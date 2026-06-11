import { useEffect, useRef, type MutableRefObject } from 'react'

/**
 * Chiusura coerente degli overlay (DESIGN.md §Dialogs: "Tap outside dismisses;
 * ESC dismisses. Never trap the user."):
 *
 * - **Escape** chiude SOLO l'overlay in cima allo stack: con sheet annidati
 *   (es. SelectSheet dentro un form) una singola pressione non deve chiudere
 *   l'intera pila.
 * - **Back del browser / BackButton Telegram**: finché almeno un overlay è
 *   aperto, una sentinella history sulla stessa URL fa sì che il back chiuda
 *   l'overlay in cima invece di lasciare la pagina (audit FE 2026-06-11, #12).
 *
 * La sentinella è UNICA per l'intero stack e viene armata/consumata in un task
 * differito (`scheduleSync`): le coppie open→close→open ravvicinate (incluso il
 * doppio effect di React StrictMode in dev) si annullano senza toccare la
 * history, evitando l'interleaving fra `history.back()` asincrono e push
 * successivi. Gli overlay non dismissible bloccano ESC e ri-armano la
 * sentinella sul back (non si esce dalla pagina a operazione in corso).
 */

interface Entry {
  id: number
  closeRef: MutableRefObject<() => void>
  dismissibleRef: MutableRefObject<boolean>
}

const SENTINEL = '__overlaySentinel'

const stack: Entry[] = []
let nextId = 1
// Pop innescati da noi (sync che consuma la sentinella): il listener popstate
// deve ignorarli, o chiuderebbe anche l'overlay successivo.
let expectedPops = 0
let sentinelArmed = false
let syncScheduled = false
let installed = false

function hasSentinel(): boolean {
  const state = window.history.state as Record<string, unknown> | null
  return Boolean(state && state[SENTINEL])
}

function scheduleSync() {
  if (syncScheduled) return
  syncScheduled = true
  // setTimeout (macrotask): gira dopo che React ha flushato render e cleanup,
  // quindi `stack` riflette lo stato assestato e non quello transitorio.
  window.setTimeout(() => {
    syncScheduled = false
    sync()
  }, 0)
}

function sync() {
  if (expectedPops > 0) {
    // Un back è ancora in volo: riprova quando la history si è assestata.
    scheduleSync()
    return
  }
  if (stack.length > 0 && !sentinelArmed) {
    // Spread dello stato corrente: HashRouter tiene i propri campi (idx, key)
    // in history.state e non devono andare persi sulla nuova entry.
    window.history.pushState({ ...window.history.state, [SENTINEL]: true }, '')
    sentinelArmed = true
  } else if (stack.length === 0 && sentinelArmed) {
    sentinelArmed = false
    // Consuma la sentinella solo se è ancora lo stato attivo: se nel frattempo
    // si è navigato altrove resta sepolta nella history ed è innocua.
    if (hasSentinel()) {
      expectedPops += 1
      window.history.back()
    }
  }
}

function handleKeyDown(event: KeyboardEvent) {
  if (event.key !== 'Escape' || stack.length === 0) return
  const top = stack[stack.length - 1]
  if (top.dismissibleRef.current) top.closeRef.current()
}

function handlePopState() {
  if (expectedPops > 0) {
    expectedPops -= 1
    return
  }
  if (!sentinelArmed || hasSentinel()) return
  // Il back dell'utente ha consumato la sentinella: chiudi l'overlay in cima
  // e ri-arma per quelli rimanenti (o per bloccare il back se non dismissible).
  sentinelArmed = false
  const top = stack[stack.length - 1]
  if (!top) return
  if (top.dismissibleRef.current) top.closeRef.current()
  scheduleSync()
}

function install() {
  if (installed) return
  installed = true
  document.addEventListener('keydown', handleKeyDown)
  window.addEventListener('popstate', handlePopState)
}

export function useOverlayDismiss(open: boolean, onClose: () => void, dismissible = true): void {
  const closeRef = useRef(onClose)
  closeRef.current = onClose
  const dismissibleRef = useRef(dismissible)
  dismissibleRef.current = dismissible

  useEffect(() => {
    if (!open) return
    install()
    const entry: Entry = { id: nextId++, closeRef, dismissibleRef }
    stack.push(entry)
    scheduleSync()

    return () => {
      const i = stack.indexOf(entry)
      if (i !== -1) stack.splice(i, 1)
      scheduleSync()
    }
  }, [open])
}

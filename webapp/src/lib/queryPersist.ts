import type { Query } from '@tanstack/react-query'
import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister'
import { removeOldestQuery, type PersistedClient, type Persister } from '@tanstack/react-query-persist-client'
import { ApiError } from '@/api/client'

/** Durata massima della cache locale: 7 giorni. Anche `gcTime` delle query salvate
 *  deve valere almeno questo, altrimenti il ripristino le scarta. */
export const CACHE_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000

/** Default 'online': da offline la query resta IN PAUSA, quindi uno skeleton infinito
 *  senza cache e nessun avviso sui dati in cache. Deve fallire. Con 'always' però
 *  TanStack spegne il refetch alla riconnessione, che va riacceso a mano: senza,
 *  l'avviso offline resta fino a un cambio pagina e una stanza di sessione aperta senza
 *  dati non riparte, perché il suo polling gira solo quando i dati ci sono. */
export const OFFLINE_QUERY_DEFAULTS = {
  networkMode: 'always',
  refetchOnReconnect: true,
} as const

// Solo ciò che serve a consultare la scheda: sessioni, cronologia, dadi e homebrew
// cambiano troppo o non servono al tavolo senza rete.
const PERSISTED_ROOTS: readonly unknown[] = ['characters', 'character', 'notes']

/** `request()` lancia `ApiError` solo se il server ha risposto: tutto il resto è rete
 *  (fetch fallito, timeout). Un `ApiError` ripristinato dalla cache è un oggetto
 *  semplice, ma conserva `status`: resta una risposta del server. */
export function isNetworkError(err: unknown): boolean {
  if (err instanceof ApiError) return false
  return typeof (err as { status?: unknown } | null | undefined)?.status !== 'number'
}

export function shouldPersistQuery(query: Query): boolean {
  if (!PERSISTED_ROOTS.includes(query.queryKey[0])) return false
  const { status, data, error, dataUpdatedAt } = query.state
  // Il maxAge del persister guarda il timestamp dell'intero client, che ogni salvataggio
  // rinfresca: una singola query vecchia non scadrebbe mai.
  if (Date.now() - dataUpdatedAt > CACHE_MAX_AGE_MS) return false
  if (status === 'success') return true
  // Ogni salvataggio riscrive l'intera cache: un refetch fallito porta la query in
  // `error`, e scartarla qui cancellerebbe la copia che si sta mostrando, lasciando
  // vuoto il ricaricamento successivo. Vale per la rete e per 401/5xx, che non dicono
  // nulla sui dati. Solo 404/403 sconfessano la copia, che va persa.
  if (status !== 'error' || data === undefined) return false
  return !(error instanceof ApiError && (error.status === 404 || error.status === 403))
}

/** Una cache per utente: stesso dispositivo, account diversi, dati separati. */
export function storageKeyFor(userId: string | number | null): string {
  return `dnd-query-cache-${userId ?? 'anon'}`
}

// In lettura un localStorage inaccessibile (WebView senza storage, permessi negati)
// si comporta da vuoto. `setItem` invece deve lanciare: il persister cattura
// l'errore e solo così scatta `removeOldestQuery` a quota esaurita.
const guardedStorage = {
  getItem(key: string): string | null {
    try {
      return window.localStorage.getItem(key)
    } catch {
      return null
    }
  },
  setItem(key: string, value: string): void {
    window.localStorage.setItem(key, value)
  },
  removeItem(key: string): void {
    try {
      window.localStorage.removeItem(key)
    } catch {
      /* niente da pulire se lo storage non è raggiungibile */
    }
  },
}

// Ciò che conta per dire se una scrittura serve: tutto tranne gli orari del salvataggio,
// che cambiano ogni volta anche con dati identici. Va fatto sulla struttura e non sul
// testo serializzato, perché anche i dati possono avere campi con questi nomi.
function comparableValue(client: PersistedClient): string {
  const { buster, clientState: { mutations, queries } } = client
  return JSON.stringify([buster, mutations, queries.map((q) => ({ ...q, dehydratedAt: 0 }))])
}

export function createPersister(userId: string | number | null): Persister {
  // Il persister salva a ogni evento della cache, compresi quelli di query non salvate:
  // nella stanza di sessione sarebbe una scrittura dell'intera cache ogni 2,5 s.
  // Senza scrittura il timestamp resta fermo, ma non è mai precedente all'ultimo
  // aggiornamento dei dati: la cache scade quando scadono loro, non prima.
  let pending = ''
  let written: string | null = null
  return createSyncStoragePersister({
    storage: {
      ...guardedStorage,
      setItem(key, value) {
        if (pending === written) return
        guardedStorage.setItem(key, value)
        written = pending
      },
      removeItem(key) {
        written = null
        guardedStorage.removeItem(key)
      },
    },
    key: storageKeyFor(userId),
    retry: removeOldestQuery,
    serialize(client) {
      pending = comparableValue(client)
      return JSON.stringify(client)
    },
  })
}

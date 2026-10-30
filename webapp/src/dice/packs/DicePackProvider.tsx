import { useEffect, useState, type ReactNode } from 'react'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import { useDiceSettings } from '@/store/diceSettings'
import type { LoadedPack } from './loader'
import { isBundledPack, type PackId } from './registry'
import { DicePackCtx } from './dicePackContext'

// Il loader importa three (~650 KB): un import statico lo metteva nel percorso
// critico di avvio (il provider è montato in App). Lo si carica on demand.
const importLoader = () => import('./loader')

// Il primo caricamento del pack (texture fino a ~22 MB) aspetta che il main
// thread sia libero: la UI parte prima, il pack è pronto ben prima del 1° tiro.
function whenIdle(cb: () => void): () => void {
  const w = window as Window & {
    requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number
    cancelIdleCallback?: (id: number) => void
  }
  if (typeof w.requestIdleCallback === 'function') {
    const id = w.requestIdleCallback(cb, { timeout: 3000 })
    return () => w.cancelIdleCallback?.(id)
  }
  const id = window.setTimeout(cb, 800)
  return () => window.clearTimeout(id)
}

export function DicePackProvider({ children }: { children: ReactNode }) {
  const packIdRaw = useDiceSettings((s) => s.packId)
  const setPackId = useDiceSettings((s) => s.setPackId)
  const animate3d = useDiceSettings((s) => s.animate3d)
  const reducedMotion = useReducedMotion()
  // Con i dadi 3D spenti non si scaricano three né le texture del pack.
  const enabled = animate3d && !reducedMotion
  const packId = isBundledPack(packIdRaw) ? packIdRaw : ('default' as PackId)
  const [pack, setPack] = useState<LoadedPack | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    const previousId: PackId | null =
      pack?.manifest.id && isBundledPack(pack.manifest.id) ? (pack.manifest.id as PackId) : null
    setLoading(true)
    setError(null)
    const load = () => {
      importLoader()
        .then(async ({ loadPackWithFallback, disposePack }) => {
          const p = await loadPackWithFallback(packId)
          if (cancelled) return
          setPack(p)
          if (previousId && previousId !== packId) disposePack(previousId)
          if (p.manifest.id !== packId) {
            setPackId(p.manifest.id)
            setError(`pack ${packId} not available, fell back to ${p.manifest.id}`)
          }
        })
        .catch((err) => {
          if (cancelled) return
          setError(String(err))
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
    }
    // Cambio pack da Settings: subito (l'utente aspetta l'anteprima).
    let cancelIdle = () => {}
    if (pack) load()
    else cancelIdle = whenIdle(load)
    return () => {
      cancelled = true
      cancelIdle()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [packId, setPackId, enabled])

  return <DicePackCtx.Provider value={{ pack, loading, error }}>{children}</DicePackCtx.Provider>
}

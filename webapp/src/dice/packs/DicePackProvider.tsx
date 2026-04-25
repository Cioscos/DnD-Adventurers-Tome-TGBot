import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { useDiceSettings } from '@/store/diceSettings'
import { loadPackWithFallback, disposePack, type LoadedPack } from './loader'
import { isBundledPack, type PackId } from './registry'

interface PackContext {
  pack: LoadedPack | null
  loading: boolean
  error: string | null
}

const Ctx = createContext<PackContext>({ pack: null, loading: false, error: null })

export function useDicePack(): PackContext {
  return useContext(Ctx)
}

export function DicePackProvider({ children }: { children: ReactNode }) {
  const packIdRaw = useDiceSettings((s) => s.packId)
  const setPackId = useDiceSettings((s) => s.setPackId)
  const packId = isBundledPack(packIdRaw) ? packIdRaw : ('default' as PackId)
  const [pack, setPack] = useState<LoadedPack | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const previousId: PackId | null =
      pack?.manifest.id && isBundledPack(pack.manifest.id) ? (pack.manifest.id as PackId) : null
    setLoading(true)
    setError(null)
    loadPackWithFallback(packId)
      .then((p) => {
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
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [packId, setPackId])

  return <Ctx.Provider value={{ pack, loading, error }}>{children}</Ctx.Provider>
}

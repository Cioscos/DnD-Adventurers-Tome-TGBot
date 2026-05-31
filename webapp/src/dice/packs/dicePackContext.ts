import { createContext, useContext } from 'react'
import type { LoadedPack } from './loader'

export interface PackContext {
  pack: LoadedPack | null
  loading: boolean
  error: string | null
}

export const DicePackCtx = createContext<PackContext>({ pack: null, loading: false, error: null })

export function useDicePack(): PackContext {
  return useContext(DicePackCtx)
}

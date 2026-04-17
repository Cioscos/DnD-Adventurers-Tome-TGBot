import { useContext } from 'react'
import { DiceAnimationContext } from './DiceAnimationProvider'
import type { DiceAnimationApi } from './types'

export function useDiceAnimation(): DiceAnimationApi {
  const ctx = useContext(DiceAnimationContext)
  if (!ctx) {
    throw new Error('useDiceAnimation must be used within a DiceAnimationProvider')
  }
  return ctx
}

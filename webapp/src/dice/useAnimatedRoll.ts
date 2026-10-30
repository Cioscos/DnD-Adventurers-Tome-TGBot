import { useCallback } from 'react'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import { useDiceSettings } from '@/store/diceSettings'
import { useDiceAnimation } from './useDiceAnimation'
import type { DiceKind } from './types'

const ANIMATED_KINDS: ReadonlySet<string> = new Set(['d4', 'd6', 'd8', 'd10', 'd12', 'd20'])

/**
 * Tiro animato per gli endpoint che accettano i dadi dal client. Restituisce le
 * facce uscite, oppure undefined se i dadi 3D sono spenti o il dado non esiste
 * in 3D (un hit die fuori standard): in quel caso tira il server.
 */
export function useAnimatedRoll() {
  const dice = useDiceAnimation()
  const animate3d = useDiceSettings((s) => s.animate3d)
  const reducedMotion = useReducedMotion()

  return useCallback(
    async (kind: string, count: number): Promise<number[] | undefined> => {
      if (!animate3d || reducedMotion || !ANIMATED_KINDS.has(kind)) return undefined
      const detected = await dice.playAndCollect([{ kind: kind as DiceKind, count }])
      return detected.map((d) => d.value)
    },
    [animate3d, dice, reducedMotion],
  )
}

import { useCallback } from 'react'
import { useDiceAnimation } from '@/dice/useDiceAnimation'
import { useDiceSettings } from '@/store/diceSettings'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import type { D20Roll, RollMode } from '@/api/client'

export type { RollMode }

/** Faces to send to the API: legacy single die for normal rolls, `{dice, mode}` for adv/dis. */
export function d20Arg(mode: RollMode, dice: number[] | undefined): D20Roll | undefined {
  return mode === 'normal' ? dice?.[0] : { dice, mode }
}

/** Animates 1 (normal) or 2 (adv/dis) d20 and returns the faces; undefined when 3D is off (server rolls). */
export function useD20Roll(): (mode: RollMode) => Promise<number[] | undefined> {
  const { playAndCollect } = useDiceAnimation()
  const animate3d = useDiceSettings((s) => s.animate3d)
  const reducedMotion = useReducedMotion()
  return useCallback(
    async (mode) => {
      if (!animate3d || reducedMotion) return undefined
      const detected = await playAndCollect([{ kind: 'd20', count: mode === 'normal' ? 1 : 2 }])
      return detected.map((d) => d.value)
    },
    [animate3d, reducedMotion, playAndCollect],
  )
}

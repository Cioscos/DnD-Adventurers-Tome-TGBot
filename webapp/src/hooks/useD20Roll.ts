import { useCallback } from 'react'
import { useDiceAnimation } from '@/dice/useDiceAnimation'
import { useDiceSettings } from '@/store/diceSettings'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import type { D20Roll, RollChoice, RollMode } from '@/api/client'

export type { RollMode }

/** Faces to send to the API: legacy single die for normal rolls, `{dice, mode}` for adv/dis or with confirmed options. */
// shortcut: con un dado salvato (Portento) il dado 3D gira comunque e il server lo ignora; il modale mostra quello giusto.
// Da togliere facendo saltare `rollD20` ai chiamanti quando la scelta ha `replace_die`.
export function d20Arg(mode: RollMode, dice: number[] | undefined, choice?: RollChoice): D20Roll | undefined {
  if (choice && (choice.options.length > 0 || choice.defer_damage)) return { dice, mode, ...choice }
  return mode === 'normal' ? dice?.[0] : { dice, mode }
}

/** Quanti d20 tirerà il server: il modo del giocatore più quelli delle opzioni scelte (Ispirazione, Spaventato); i due opposti si annullano. */
export function d20Count(mode: RollMode, choice?: RollChoice): 1 | 2 {
  const adv = mode === 'advantage' || !!choice?.modes?.includes('advantage')
  const dis = mode === 'disadvantage' || !!choice?.modes?.includes('disadvantage')
  return adv !== dis ? 2 : 1
}

/** Animates 1 (normal) or 2 (adv/dis, also from the chosen options) d20 and returns the faces; undefined when 3D is off (server rolls). */
export function useD20Roll(): (mode: RollMode, choice?: RollChoice) => Promise<number[] | undefined> {
  const { playAndCollect } = useDiceAnimation()
  const animate3d = useDiceSettings((s) => s.animate3d)
  const reducedMotion = useReducedMotion()
  return useCallback(
    async (mode, choice) => {
      if (!animate3d || reducedMotion) return undefined
      const detected = await playAndCollect([{ kind: 'd20', count: d20Count(mode, choice) }])
      return detected.map((d) => d.value)
    },
    [animate3d, reducedMotion, playAndCollect],
  )
}

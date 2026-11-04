import { useState, type ReactNode } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, ApiError, type D20Roll } from '@/api/client'
import { useAnimatedRoll } from '@/dice/useAnimatedRoll'
import { useD20Roll, d20Arg, type RollMode } from '@/hooks/useD20Roll'
import { useToast } from '@/hooks/useToast'
import { haptic } from '@/auth/telegram'
import type { WeaponChoice } from '@/lib/weaponOptions'
import { useWeaponChoices, choiceOf } from '@/store/weaponChoiceStore'
import WeaponAttackModal from '@/components/WeaponAttackModal'
import { askRollOptions } from '@/lib/rollOptions'
import type { RollOptionsQuery } from '@/api/client'
import type { WeaponAttackResult } from '@/components/WeaponAttackModal'
import type { CharacterFull } from '@/types'

type AttackSource = { type: 'weapon'; itemId: number; choice: WeaponChoice } | { type: 'unarmed' }
type AttackState = { result: WeaponAttackResult; source: AttackSource; wasRerolled: boolean }

export interface WeaponAttackFlow {
  attackWeapon: (itemId: number, mode: RollMode) => void
  attackUnarmed: (mode: RollMode) => void
  isWeaponPending: (itemId: number) => boolean
  isUnarmedPending: boolean
  /** Il chiamante monta il modal di esito una volta nel proprio JSX. */
  elements: ReactNode
}

/** L'attacco con la conferma al tiro: opzioni prima del d20 e, se ce ne sono dopo il colpo, secondo tempo del danno.
 *  `null`: il giocatore ha dichiarato il mancato. */
export function useAttackRoll() {
  const { t } = useTranslation()
  const rollD20 = useD20Roll()
  return async (
    charId: number, itemId: number | null, mode: RollMode, inspiration: boolean, choice?: WeaponChoice,
  ): Promise<WeaponAttackResult | null> => {
    const query: RollOptionsQuery = itemId === null ? { roll: 'attack' } : { roll: 'attack', item_id: itemId }
    const post = (reroll: boolean, roll: D20Roll | undefined) => (itemId === null
      ? api.items.attackUnarmed(charId, reroll, roll)
      : api.items.attack(charId, itemId, reroll, roll, choice))
    const before = await askRollOptions(charId, query)
    let result = await post(false, d20Arg(mode, await rollD20(mode), before))
    let canReroll = inspiration
    while (result.attack_id) {
      const summary = t('character.roll_options.summary', {
        total: result.to_hit_total, die: result.to_hit_die, bonus: result.to_hit_bonus,
      }) + (result.is_critical ? ` · ${t('character.dice.critical_banner')}` : '')
      const after = await askRollOptions(charId, query, 'after_hit', { summary, canReroll })
      if (after.outcome === 'miss') return null
      if (after.outcome !== 'reroll') return api.items.attackDamage(charId, result.attack_id, after)
      canReroll = false
      result = await post(true, { dice: await rollD20('normal'), mode: 'normal', defer_damage: true })
    }
    return result
  }
}

/** Flusso di attacco condiviso fra Azioni e vista Turno: tiro d20, esito, reroll con ispirazione. */
export function useWeaponAttackFlow(charId: number, char: CharacterFull | undefined): WeaponAttackFlow {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [attackState, setAttackState] = useState<AttackState | null>(null)
  const choices = useWeaponChoices((s) => s.choices)
  const rollDice = useAnimatedRoll()
  const attackRoll = useAttackRoll()
  const inspiration = !!char?.heroic_inspiration

  const weaponAttack = useMutation({
    mutationFn: ({ itemId, mode }: { itemId: number; mode: RollMode }) =>
      attackRoll(charId, itemId, mode, inspiration, choiceOf(choices, itemId)),
    onSuccess: (result, { itemId }) => {
      if (result) {
        setAttackState({
          result, source: { type: 'weapon', itemId, choice: choiceOf(choices, itemId) }, wasRerolled: false,
        })
      }
      qc.invalidateQueries({ queryKey: ['character', charId] })
      qc.invalidateQueries({ queryKey: ['turn-state', charId] })
      haptic.success()
    },
  })

  const unarmedAttack = useMutation({
    mutationFn: (mode: RollMode) => attackRoll(charId, null, mode, inspiration),
    onSuccess: (result) => {
      if (result) setAttackState({ result, source: { type: 'unarmed' }, wasRerolled: false })
      qc.invalidateQueries({ queryKey: ['character', charId] })
      qc.invalidateQueries({ queryKey: ['turn-state', charId] })
      haptic.success()
    },
  })

  const rerollAttack = useMutation({
    mutationFn: async (source: AttackSource) => {
      const die = (await rollDice('d20', 1))?.[0]
      return source.type === 'weapon'
        ? api.items.attack(charId, source.itemId, true, die, source.choice)
        : api.items.attackUnarmed(charId, true, die)
    },
    onSuccess: (result) => {
      setAttackState((prev) => prev && { ...prev, result, wasRerolled: true })
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.success()
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        toast.error(t('character.inspiration.unavailable_error'))
        qc.invalidateQueries({ queryKey: ['character', charId] })
      } else {
        haptic.error()
      }
    },
  })

  const elements = attackState && (
    <WeaponAttackModal
      result={attackState.result}
      onClose={() => setAttackState(null)}
      inspirationAvailable={!!char?.heroic_inspiration}
      isRerolling={rerollAttack.isPending}
      wasRerolled={attackState.wasRerolled}
      onInspirationReroll={() => rerollAttack.mutate(attackState.source)}
    />
  )

  return {
    attackWeapon: (itemId, mode) => weaponAttack.mutate({ itemId, mode }),
    attackUnarmed: (mode) => unarmedAttack.mutate(mode),
    isWeaponPending: (itemId) => weaponAttack.isPending && weaponAttack.variables?.itemId === itemId,
    isUnarmedPending: unarmedAttack.isPending,
    elements,
  }
}

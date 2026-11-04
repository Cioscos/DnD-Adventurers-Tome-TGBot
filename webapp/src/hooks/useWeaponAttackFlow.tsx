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
import { askRollOptions, hasAfterHitOptions } from '@/lib/rollOptions'
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
  const toast = useToast()
  const rollD20 = useD20Roll()
  const rollDice = useAnimatedRoll()

  const flow = (charId: number, itemId: number | null, choice?: WeaponChoice) => {
    const query: RollOptionsQuery = itemId === null
      ? { roll: 'attack' }
      : { roll: 'attack', item_id: itemId, attack_mode: choice?.attack_mode, grip: choice?.grip }
    const post = (reroll: boolean, roll: D20Roll | undefined) => (itemId === null
      ? api.items.attackUnarmed(charId, reroll, roll)
      : api.items.attack(charId, itemId, reroll, roll, choice))
    const secondStep = async (first: WeaponAttackResult, inspiration: boolean): Promise<WeaponAttackResult | null> => {
      let result = first
      let canReroll = inspiration
      while (result.attack_id) {
        const bonus = `${result.to_hit_bonus >= 0 ? '+' : ''}${result.to_hit_bonus}`
        const summary = t('character.roll_options.summary', { total: result.to_hit_total, die: result.to_hit_die, bonus })
          + (result.is_critical ? ` · ${t('character.dice.critical_banner')}` : '')
        const after = await askRollOptions(charId, query, 'after_hit', { summary, canReroll })
        if (after.outcome === 'miss') return null
        if (after.outcome !== 'reroll') {
          try {
            return await api.items.attackDamage(charId, result.attack_id, after)
          } catch {
            // Il d20 e il danno base sono già tirati e registrati: si mostrano quelli, non si perde l'attacco.
            toast.warning(t('character.roll_options.damage_failed'))
            return result
          }
        }
        canReroll = false
        result = await post(true, { dice: await rollD20('normal'), mode: 'normal', defer_damage: true })
      }
      return result
    }
    return { query, post, secondStep }
  }

  return {
    roll: async (
      charId: number, itemId: number | null, mode: RollMode, inspiration: boolean, choice?: WeaponChoice,
    ): Promise<WeaponAttackResult | null> => {
      const { query, post, secondStep } = flow(charId, itemId, choice)
      const before = await askRollOptions(charId, query)
      return secondStep(await post(false, d20Arg(mode, await rollD20(mode), before)), inspiration)
    },
    /** Ritira con l'ispirazione dal modal di esito: anche dopo un 1 naturale il secondo tempo va proposto. */
    reroll: async (charId: number, itemId: number | null, choice?: WeaponChoice): Promise<WeaponAttackResult | null> => {
      const { query, post, secondStep } = flow(charId, itemId, choice)
      const deferred = await hasAfterHitOptions(charId, query)
      const dice = await rollDice('d20', 1)
      if (!deferred) return post(true, dice?.[0])
      return secondStep(await post(true, { dice, mode: 'normal', defer_damage: true }), false)
    },
  }
}

/** Flusso di attacco condiviso fra Azioni e vista Turno: tiro d20, esito, reroll con ispirazione. */
export function useWeaponAttackFlow(charId: number, char: CharacterFull | undefined): WeaponAttackFlow {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [attackState, setAttackState] = useState<AttackState | null>(null)
  const choices = useWeaponChoices((s) => s.choices)
  const attack = useAttackRoll()
  const inspiration = !!char?.heroic_inspiration

  const weaponAttack = useMutation({
    mutationFn: ({ itemId, mode }: { itemId: number; mode: RollMode }) =>
      attack.roll(charId, itemId, mode, inspiration, choiceOf(choices, itemId)),
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
    mutationFn: (mode: RollMode) => attack.roll(charId, null, mode, inspiration),
    onSuccess: (result) => {
      if (result) setAttackState({ result, source: { type: 'unarmed' }, wasRerolled: false })
      qc.invalidateQueries({ queryKey: ['character', charId] })
      qc.invalidateQueries({ queryKey: ['turn-state', charId] })
      haptic.success()
    },
  })

  const rerollAttack = useMutation({
    mutationFn: (source: AttackSource) => (source.type === 'weapon'
      ? attack.reroll(charId, source.itemId, source.choice)
      : attack.reroll(charId, null)),
    onSuccess: (result) => {
      setAttackState((prev) => (result && prev ? { ...prev, result, wasRerolled: true } : null))
      qc.invalidateQueries({ queryKey: ['character', charId] })
      qc.invalidateQueries({ queryKey: ['turn-state', charId] })
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

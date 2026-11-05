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
import { applyAfterRoll, askAttackLimit, askRollOptions, canRerollInspiration, hasDeferringOptions } from '@/lib/rollOptions'
import type { RollOptionsQuery } from '@/api/client'
import type { WeaponAttackResult } from '@/components/WeaponAttackModal'
import type { CharacterFull } from '@/types'

type AttackSource = { type: 'weapon'; itemId: number; choice: WeaponChoice } | { type: 'unarmed' }
type UnarmedEffect = 'grapple' | 'shove'
type AttackState = { result: WeaponAttackResult; source: AttackSource; wasRerolled: boolean }

export interface WeaponAttackFlow {
  /** `preset`: opzioni già scelte (reazione in un tocco), senza passare dal prompt. */
  attackWeapon: (itemId: number, mode: RollMode, preset?: string[]) => void
  attackUnarmed: (mode: RollMode, preset?: string[]) => void
  /** Colpo senz'armi 2024: afferrare o spingere, senza tiro per colpire. */
  attackUnarmedEffect: (effect: UnarmedEffect) => void
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

  /** Oltre il limite dell'azione Attacco si passa solo confermando. `null`: il giocatore ha rinunciato. */
  const limitConfirmation = async (charId: number): Promise<{ confirm_extra_attack?: true } | null> => {
    const state = await api.characters.turnState(charId).catch(() => null)
    if (!state || state.turn.action_attacks < state.attacks_allowed) return {}
    return (await askAttackLimit(state.turn.action_attacks, state.attacks_allowed)) ? { confirm_extra_attack: true } : null
  }

  /** Il server può rifiutare ciò che la pagina non aveva ancora visto: lo si dice, senza errori muti. */
  const refused = (err: unknown): boolean => {
    const code = err instanceof ApiError ? (err.detail as { code?: string } | null)?.code : undefined
    if (code === 'incapacitated') toast.error(t('character.attack.incapacitated'))
    else if (code === 'attack_limit') toast.error(t('character.attack.limit_title'))
    else if (code === 'turn_slot_used') toast.error(t('character.attack.bonus_used'))
    else return false
    return true
  }

  const flow = (charId: number, itemId: number | null, choice?: WeaponChoice, confirm?: { confirm_extra_attack?: true }, ranged?: boolean) => {
    const query: RollOptionsQuery = itemId === null
      ? { roll: 'attack', ...(ranged ? { attack_mode: 'thrown' } : {}) }
      : { roll: 'attack', item_id: itemId, attack_mode: choice?.attack_mode, grip: choice?.grip, ability: choice?.ability }
    const confirmed = confirm?.confirm_extra_attack ? confirm : undefined
    const post = (reroll: boolean, roll: D20Roll | undefined) => (itemId === null
      ? api.items.attackUnarmed(charId, reroll, roll, confirmed)
      : api.items.attack(charId, itemId, reroll, roll, confirmed ? { ...choice, ...confirmed } : choice))
    const secondStep = async (first: WeaponAttackResult, inspiration: boolean): Promise<WeaponAttackResult | null> => {
      let result = first
      let canReroll = inspiration
      let refundable = false  // dichiarare il mancato restituisce ciò che si paga solo se il tiro riesce
      let used: string[] = []
      while (result.attack_id) {
        const bonus = `${result.to_hit_bonus >= 0 ? '+' : ''}${result.to_hit_bonus}`
        const summary = t('character.roll_options.summary', { total: result.to_hit_total, die: result.to_hit_die, bonus })
          + (result.is_critical ? ` · ${t('character.dice.critical_banner')}` : '')
          + (result.is_fumble ? ` · ${t('character.dice.fumble_banner')}` : '')
          + (result.forced_hit ? ` · ${t('character.roll_options.forced_hit')}` : '')
        const after = await askRollOptions(charId, query, 'after_hit', {
          summary, canReroll, fumble: result.is_fumble, used, keepOpen: used.length > 0,
        })
        // Su un 1 naturale non c'è danno da chiedere: anche senza più opzioni l'esito è il mancato.
        if (after.outcome === 'miss' || (result.is_fumble && !after.outcome)) {
          if (refundable) await api.characters.lastRollRefund(charId).catch(() => toast.warning(t('character.roll_options.refund_failed')))
          return result.is_fumble ? { ...result, attack_id: undefined } : null
        }
        if (after.outcome === 'after_roll') {
          try {
            const updated = await applyAfterRoll(charId, after.after_option!, rollD20)
            result = updated.attack!
            refundable = refundable || !!updated.refundable?.length
            used = [...used, after.after_option!.key]
          } catch {
            toast.warning(t('character.roll_options.after_roll_failed'))
          }
          continue
        }
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
        refundable = false
        used = []
        result = await post(true, { dice: await rollD20('normal'), mode: 'normal', defer_damage: true })
      }
      return result
    }
    return { query, post, secondStep }
  }

  return {
    roll: async (
      charId: number, itemId: number | null, mode: RollMode, inspiration: boolean, choice?: WeaponChoice,
      preset?: string[],
    ): Promise<WeaponAttackResult | null> => {
      const offhand = choice?.attack_mode === 'offhand'
      // Prima le opzioni: una con uno slot proprio (Frenesia, Ritorsione) non pesa sul limite dell'azione Attacco.
      const { query: optionsQuery } = flow(charId, itemId, choice)
      const { own_slot, ranged, ...before } = await askRollOptions(charId, optionsQuery, 'before', preset ? { preset } : undefined)
      const confirm = offhand || own_slot ? {} : await limitConfirmation(charId)
      if (!confirm) return null
      const { post, secondStep } = flow(charId, itemId, choice, confirm, ranged)
      const dice = await rollD20(mode)
      let first: WeaponAttackResult
      try {
        first = await post(false, d20Arg(mode, dice, before))
      } catch (err) {
        if (refused(err)) return null
        throw err
      }
      // L'altra mano vale per un attacco: il prossimo torna normale.
      if (offhand && itemId !== null) useWeaponChoices.getState().setChoice(itemId, { ...choice!, attack_mode: 'melee' })
      return secondStep(first, inspiration)
    },
    unarmedEffect: async (charId: number, effect: UnarmedEffect): Promise<WeaponAttackResult | null> => {
      const confirm = await limitConfirmation(charId)
      if (!confirm) return null
      try {
        return await api.items.attackUnarmed(charId, false, undefined, { effect, ...confirm })
      } catch (err) {
        if (refused(err)) return null
        throw err
      }
    },
    /** Ritira con l'ispirazione dal modal di esito: anche dopo un 1 naturale il secondo tempo va proposto. */
    reroll: async (charId: number, itemId: number | null, choice?: WeaponChoice): Promise<WeaponAttackResult | null> => {
      const { query, post, secondStep } = flow(charId, itemId, choice)
      const deferred = await hasDeferringOptions(charId, query)
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
  const inspiration = canRerollInspiration(char)

  const weaponAttack = useMutation({
    // La scelta usata per il rilancio è quella del tiro: l'altra mano si spegne dopo il primo.
    onMutate: ({ itemId }: { itemId: number; mode: RollMode; preset?: string[] }) => ({ choice: choiceOf(choices, itemId) }),
    mutationFn: ({ itemId, mode, preset }: { itemId: number; mode: RollMode; preset?: string[] }) =>
      attack.roll(charId, itemId, mode, inspiration, choiceOf(choices, itemId), preset),
    onSuccess: (result, { itemId }, context) => {
      if (result) {
        setAttackState({
          result, source: { type: 'weapon', itemId, choice: context.choice }, wasRerolled: false,
        })
      }
      qc.invalidateQueries({ queryKey: ['character', charId] })
      qc.invalidateQueries({ queryKey: ['turn-state', charId] })
      haptic.success()
    },
  })

  const unarmedAttack = useMutation({
    mutationFn: ({ mode, preset }: { mode: RollMode; preset?: string[] }) =>
      attack.roll(charId, null, mode, inspiration, undefined, preset),
    onSuccess: (result) => {
      if (result) setAttackState({ result, source: { type: 'unarmed' }, wasRerolled: false })
      qc.invalidateQueries({ queryKey: ['character', charId] })
      qc.invalidateQueries({ queryKey: ['turn-state', charId] })
      haptic.success()
    },
  })

  const unarmedEffect = useMutation({
    mutationFn: (effect: UnarmedEffect) => attack.unarmedEffect(charId, effect),
    onSuccess: (result) => {
      if (result) setAttackState({ result, source: { type: 'unarmed' }, wasRerolled: false })
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
      charId={charId}
      onClose={() => setAttackState(null)}
      inspirationAvailable={inspiration}
      isRerolling={rerollAttack.isPending}
      wasRerolled={attackState.wasRerolled}
      onInspirationReroll={() => rerollAttack.mutate(attackState.source)}
    />
  )

  return {
    attackWeapon: (itemId, mode, preset) => weaponAttack.mutate({ itemId, mode, preset }),
    attackUnarmed: (mode, preset) => unarmedAttack.mutate({ mode, preset }),
    attackUnarmedEffect: (effect) => unarmedEffect.mutate(effect),
    isWeaponPending: (itemId) => weaponAttack.isPending && weaponAttack.variables?.itemId === itemId,
    isUnarmedPending: unarmedAttack.isPending,
    elements,
  }
}

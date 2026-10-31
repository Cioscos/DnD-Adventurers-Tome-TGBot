import { useState, type ReactNode } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, ApiError } from '@/api/client'
import { useAnimatedRoll } from '@/dice/useAnimatedRoll'
import { useD20Roll, d20Arg, type RollMode } from '@/hooks/useD20Roll'
import { useToast } from '@/hooks/useToast'
import { haptic } from '@/auth/telegram'
import type { WeaponChoice } from '@/lib/weaponOptions'
import { useWeaponChoices, choiceOf } from '@/store/weaponChoiceStore'
import WeaponAttackModal from '@/components/WeaponAttackModal'
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

/** Flusso di attacco condiviso fra Azioni e vista Turno: tiro d20, esito, reroll con ispirazione. */
export function useWeaponAttackFlow(charId: number, char: CharacterFull | undefined): WeaponAttackFlow {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [attackState, setAttackState] = useState<AttackState | null>(null)
  const choices = useWeaponChoices((s) => s.choices)
  const rollDice = useAnimatedRoll()
  const rollD20 = useD20Roll()

  const weaponAttack = useMutation({
    mutationFn: async ({ itemId, mode }: { itemId: number; mode: RollMode }) => {
      const choice = choiceOf(choices, itemId)
      return api.items.attack(charId, itemId, false, d20Arg(mode, await rollD20(mode)), choice)
    },
    onSuccess: (result, { itemId }) => {
      setAttackState({
        result, source: { type: 'weapon', itemId, choice: choiceOf(choices, itemId) }, wasRerolled: false,
      })
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.success()
    },
  })

  const unarmedAttack = useMutation({
    mutationFn: async (mode: RollMode) =>
      api.items.attackUnarmed(charId, false, d20Arg(mode, await rollD20(mode))),
    onSuccess: (result) => {
      setAttackState({ result, source: { type: 'unarmed' }, wasRerolled: false })
      qc.invalidateQueries({ queryKey: ['character', charId] })
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

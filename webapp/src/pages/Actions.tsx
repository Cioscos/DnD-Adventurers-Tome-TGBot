import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { GiFist, GiCrossedSwords } from 'react-icons/gi'
import { Target } from 'lucide-react'
import { api, ApiError } from '@/api/client'
import { useAnimatedRoll } from '@/dice/useAnimatedRoll'
import { unarmedDamageDice } from '@/lib/unarmedStrike'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import SectionDivider from '@/components/ui/SectionDivider'
import RollButton from '@/components/ui/RollButton'
import WeaponChoiceRow from '@/components/WeaponChoiceRow'
import { useD20Roll, d20Arg, type RollMode } from '@/hooks/useD20Roll'
import type { WeaponChoice } from '@/lib/weaponOptions'
import { useWeaponChoices, choiceOf } from '@/store/weaponChoiceStore'
import WeaponAttackModal from '@/components/WeaponAttackModal'
import type { WeaponAttackResult } from '@/components/WeaponAttackModal'
import ActionsSkeleton from '@/components/skeletons/ActionsSkeleton'
import { haptic } from '@/auth/telegram'
import { useToast } from '@/hooks/useToast'

type AttackSource = { type: 'weapon'; itemId: number; choice: WeaponChoice } | { type: 'unarmed' }
type AttackState = { result: WeaponAttackResult; source: AttackSource; wasRerolled: boolean }

export default function Actions() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [attackState, setAttackState] = useState<AttackState | null>(null)
  // Scelta pre-attacco ricordata per arma (una/due mani, mischia/lancio), condivisa fra le pagine.
  const choices = useWeaponChoices((s) => s.choices)
  const setChoice = useWeaponChoices((s) => s.setChoice)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

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

  if (!char) {
    return (
      <Layout title={t('character.actions.title')} backTo={`/char/${charId}`} group="combat" page="actions">
        <ActionsSkeleton />
      </Layout>
    )
  }

  const weapons = (char.items ?? []).filter((i) => i.item_type === 'weapon' && i.is_equipped)
  const unarmedDamage = unarmedDamageDice(char.classes)

  return (
    <Layout title={t('character.actions.title')} backTo={`/char/${charId}`} group="combat" page="actions">
      <Surface variant="elevated" ornamented>
        <div className="flex items-center gap-3">
          <GiFist size={28} className="text-dnd-gold-bright shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="font-cinzel text-dnd-gold">{t('character.actions.unarmed')}</p>
            <p className="text-xs text-dnd-text-muted">{t('character.actions.unarmed_desc', { damage: unarmedDamage })}</p>
          </div>
          <RollButton
            onRoll={(mode) => unarmedAttack.mutate(mode)}
            pending={unarmedAttack.isPending}
            ariaLabel={t('character.actions.unarmed')}
            className="flex items-center gap-1 text-sm font-medium px-4 h-11 rounded-lg bg-dnd-crimson/20 text-dnd-crimson-bright border border-dnd-crimson/30 active:scale-95 transition-transform"
          >
            <Target size={14} />
            {t('character.actions.attack')}
          </RollButton>
        </div>
      </Surface>

      <SectionDivider icon={<GiCrossedSwords size={11} />} align="center">
        {t('character.actions.weapons_section')}
      </SectionDivider>

      {weapons.length === 0 ? (
        <p className="text-center text-sm text-dnd-text-muted py-2">{t('character.actions.no_weapons')}</p>
      ) : (
        <div className="space-y-2">
          {weapons.map((w) => (
            <Surface key={w.id} variant="elevated">
              <div className="flex items-center gap-3">
                <GiCrossedSwords size={22} className="text-dnd-gold shrink-0" />
                <span className="flex-1 min-w-0 truncate">{w.name}</span>
                <RollButton
                  onRoll={(mode) => weaponAttack.mutate({ itemId: w.id, mode })}
                  pending={weaponAttack.isPending && weaponAttack.variables?.itemId === w.id}
                  ariaLabel={`${t('character.actions.attack')} ${w.name}`}
                  className="flex items-center gap-1 text-sm font-medium px-4 h-11 rounded-lg bg-dnd-crimson/20 text-dnd-crimson-bright border border-dnd-crimson/30 active:scale-95 transition-transform"
                >
                  <Target size={14} />
                  {t('character.actions.attack')}
                </RollButton>
              </div>
              <WeaponChoiceRow
                item={w}
                choice={choiceOf(choices, w.id)}
                onChange={(c) => setChoice(w.id, c)}
              />
            </Surface>
          ))}
        </div>
      )}

      {attackState && (
        <WeaponAttackModal
          result={attackState.result}
          onClose={() => setAttackState(null)}
          inspirationAvailable={!!char.heroic_inspiration}
          isRerolling={rerollAttack.isPending}
          wasRerolled={attackState.wasRerolled}
          onInspirationReroll={() => rerollAttack.mutate(attackState.source)}
        />
      )}
    </Layout>
  )
}

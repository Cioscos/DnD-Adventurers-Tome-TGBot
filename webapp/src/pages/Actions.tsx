import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { GiFist, GiCrossedSwords } from 'react-icons/gi'
import { Target } from 'lucide-react'
import { api } from '@/api/client'
import { unarmedDamageDice } from '@/lib/unarmedStrike'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import SectionDivider from '@/components/ui/SectionDivider'
import RollButton from '@/components/ui/RollButton'
import WeaponChoiceRow from '@/components/WeaponChoiceRow'
import { useWeaponChoices, choiceOf } from '@/store/weaponChoiceStore'
import { useWeaponAttackFlow } from '@/hooks/useWeaponAttackFlow'
import ActionsSkeleton from '@/components/skeletons/ActionsSkeleton'

export default function Actions() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  // Scelta pre-attacco ricordata per arma (una/due mani, mischia/lancio), condivisa fra le pagine.
  const choices = useWeaponChoices((s) => s.choices)
  const setChoice = useWeaponChoices((s) => s.setChoice)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const flow = useWeaponAttackFlow(charId, char)

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
      <p className="text-center text-sm text-dnd-text font-body tabular-nums">
        {t('character.actions.attacks_per_action', { n: char.attacks_per_action ?? 1 })}
      </p>

      <Surface variant="elevated" ornamented>
        <div className="flex items-center gap-3">
          <GiFist size={28} className="text-dnd-gold-bright shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="font-cinzel text-dnd-gold">{t('character.actions.unarmed')}</p>
            <p className="text-xs text-dnd-text-muted">{t('character.actions.unarmed_desc', { damage: unarmedDamage })}</p>
          </div>
          <RollButton
            onRoll={(mode) => flow.attackUnarmed(mode)}
            pending={flow.isUnarmedPending}
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
                  onRoll={(mode) => flow.attackWeapon(w.id, mode)}
                  pending={flow.isWeaponPending(w.id)}
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

      {flow.elements}
    </Layout>
  )
}

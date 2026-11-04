import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { GiFist, GiCrossedSwords } from 'react-icons/gi'
import { Target } from 'lucide-react'
import { api } from '@/api/client'
import { unarmedDamageDice } from '@/lib/unarmedStrike'
import Layout from '@/components/Layout'
import RollButton from '@/components/ui/RollButton'
import WeaponChoiceRow from '@/components/WeaponChoiceRow'
import { useWeaponChoices, choiceOf } from '@/store/weaponChoiceStore'
import { useWeaponAttackFlow } from '@/hooks/useWeaponAttackFlow'
import ActionsSkeleton from '@/components/skeletons/ActionsSkeleton'
import { LEDGER_TITLE } from '@/styles/ledger'

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

      <div className="border-y border-dnd-border px-1 py-2">
        {/* Sotto 375px "Attacca" va a capo a tutta larghezza invece di schiacciare titolo e descrizione */}
        <div className="flex flex-wrap items-center gap-3">
          <GiFist size={22} aria-hidden className="text-dnd-gold shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="font-body text-sm font-semibold text-dnd-text">{t('character.actions.unarmed')}</p>
            <p className="text-xs text-dnd-text-muted">{t('character.actions.unarmed_desc', { damage: unarmedDamage })}</p>
          </div>
          <RollButton
            onRoll={(mode) => flow.attackUnarmed(mode)}
            pending={flow.isUnarmedPending}
            ariaLabel={t('character.actions.unarmed')}
            className="max-xs:w-full justify-center flex items-center gap-1 text-sm font-medium px-4 h-11 rounded-lg bg-dnd-crimson/10 text-dnd-crimson-bright border border-dnd-crimson/30 active:scale-95 transition-transform"
          >
            <Target size={14} />
            {t('character.actions.attack')}
          </RollButton>
        </div>
      </div>

      <h2 className={`-mb-2 mt-1 pl-1 ${LEDGER_TITLE}`}>
        {t('character.actions.weapons_section')}
      </h2>

      {weapons.length === 0 ? (
        <p className="text-center text-sm text-dnd-text-muted py-2">{t('character.actions.no_weapons')}</p>
      ) : (
        <div className="border-y border-dnd-border divide-y divide-dnd-border/60">
          {weapons.map((w) => (
            <div key={w.id} className="px-1 py-2">
              <div className="flex items-center gap-3">
                <GiCrossedSwords size={22} aria-hidden className="text-dnd-gold shrink-0" />
                <span className="flex-1 min-w-0 truncate font-body text-sm font-semibold text-dnd-text">{w.name}</span>
                <RollButton
                  onRoll={(mode) => flow.attackWeapon(w.id, mode)}
                  pending={flow.isWeaponPending(w.id)}
                  ariaLabel={`${t('character.actions.attack')} ${w.name}`}
                  className="flex items-center gap-1 text-sm font-medium px-4 h-11 rounded-lg bg-dnd-crimson/10 text-dnd-crimson-bright border border-dnd-crimson/30 active:scale-95 transition-transform"
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
            </div>
          ))}
        </div>
      )}

      {flow.elements}
    </Layout>
  )
}

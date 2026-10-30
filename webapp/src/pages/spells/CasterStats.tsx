import { useTranslation } from 'react-i18next'
import type { SpellcastingInfo } from '@/types'

type Caster = SpellcastingInfo['casters'][number]

/** Una riga per classe incantatrice: CD del tiro salvezza e bonus di attacco. */
export default function CasterStats({ casters }: { casters: Caster[] }) {
  const { t } = useTranslation()
  if (casters.length === 0) return null

  return (
    <div className="rounded-xl border border-dnd-border bg-dnd-surface-raised px-3 py-2 space-y-1">
      {casters.map((c) => {
        const ability = t(`common.abilities.${c.ability.toLowerCase()}`, { defaultValue: c.ability })
        const cls = t(`dnd.classes.${c.class_name.toLowerCase()}`, { defaultValue: c.class_name })
        const attack = `${c.attack_bonus >= 0 ? '+' : '-'}${Math.abs(c.attack_bonus)}`
        return (
          <p key={c.class_id} className="text-sm font-body text-dnd-text tabular-nums">
            {t('character.spells.caster_row', { class: cls, ability, dc: c.save_dc, attack })}
          </p>
        )
      })}
    </div>
  )
}

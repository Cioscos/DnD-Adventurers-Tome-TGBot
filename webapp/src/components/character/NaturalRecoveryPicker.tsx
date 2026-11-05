import { Minus, Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import IconButton from '@/components/ui/IconButton'
import { classKey } from '@/lib/classProgression'
import type { CharacterFull } from '@/types'

const MAX_LEVEL = 5

/** Livelli di slot recuperabili: metà del livello da druido, per eccesso (specchio di `api/services/natural_recovery.py`). */
const recoveryBudget = (druidLevel: number) => Math.ceil(druidLevel / 2)

/** Recupero Naturale (Druido 2014, Circolo della Terra) nel foglio del riposo breve: quali slot spesi riprendere. Il server
 *  ricontrolla tutto (tetto, slot davvero spesi, un solo uso) e rifiuta il riposo intero se qualcosa non torna. */
export default function NaturalRecoveryPicker({ char, value, onChange }: {
  char: CharacterFull
  value: Record<number, number>
  onChange: (next: Record<number, number>) => void
}) {
  const { t } = useTranslation()
  const ability = (char.abilities ?? []).find((a) => a.feature_key === 'druid.natural_recovery')
  const druidLevel = (char.classes ?? []).filter((c) => classKey(c.class_name) === 'druid').reduce((n, c) => n + c.level, 0)
  const spent = (char.spell_slots ?? []).filter((s) => !s.is_pact && s.level <= MAX_LEVEL && s.used > 0)
  if (!ability || (ability.max_uses != null && (ability.uses ?? 0) < 1) || druidLevel < 1 || spent.length === 0) return null

  const used = Object.entries(value).reduce((n, [lv, count]) => n + Number(lv) * count, 0)
  const left = recoveryBudget(druidLevel) - used
  const set = (level: number, count: number) => {
    const next = { ...value, [level]: count }
    if (count <= 0) delete next[level]
    onChange(next)
  }

  return (
    <section data-testid="natural-recovery" className="space-y-2 text-left">
      <h3 className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">{t('character.quick_actions.natural_recovery')}</h3>
      <p className="text-sm font-body text-dnd-text">
        {t('character.quick_actions.natural_recovery_hint')}{' '}
        <span data-testid="nr-left" className="font-mono tabular-nums font-bold">{left}</span>
      </p>
      <ul className="space-y-1.5">
        {spent.map((s) => {
          const count = value[s.level] ?? 0
          return (
            <li key={s.level} className="flex items-center gap-2">
              <span className="flex-1 text-sm font-body text-dnd-text">
                {t('character.quick_actions.natural_recovery_slot', { level: s.level, spent: s.used })}
              </span>
              <span data-testid={`nr-minus-${s.level}`}>
                <IconButton variant="secondary" className="min-h-11 min-w-11" icon={<Minus size={16} />} disabled={count === 0}
                  aria-label={t('character.quick_actions.natural_recovery_less', { level: s.level })} onClick={() => set(s.level, count - 1)} />
              </span>
              <span data-testid={`nr-count-${s.level}`} className="w-6 text-center font-mono tabular-nums font-bold">{count}</span>
              <span data-testid={`nr-plus-${s.level}`}>
                <IconButton variant="secondary" className="min-h-11 min-w-11" icon={<Plus size={16} />} disabled={count >= s.used || s.level > left}
                  aria-label={t('character.quick_actions.natural_recovery_more', { level: s.level })} onClick={() => set(s.level, count + 1)} />
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

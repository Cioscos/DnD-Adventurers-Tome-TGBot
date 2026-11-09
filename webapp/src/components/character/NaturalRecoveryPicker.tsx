import { Minus, Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import IconButton from '@/components/ui/IconButton'
import { classKey } from '@/lib/classProgression'
import type { CharacterFull } from '@/types'

const MAX_LEVEL = 5

/** Livelli di slot recuperabili: metà del livello della classe, per eccesso (specchio di `api/services/natural_recovery.py`). */
const recoveryBudget = (classLevel: number) => Math.ceil(classLevel / 2)

/** Quale privilegio di recupero degli slot, di quale classe, con quali chiavi di testo: il Recupero Naturale del Druido o il
 *  Recupero Arcano del Mago hanno le stesse regole e lo stesso endpoint. */
interface RecoveryKind { feature: string; cls: string; keyPrefix: string; testId: string; idPrefix: string }
const NATURAL: RecoveryKind = { feature: 'druid.natural_recovery', cls: 'druid', keyPrefix: 'natural_recovery', testId: 'natural-recovery', idPrefix: 'nr' }
const ARCANE: RecoveryKind = { feature: 'wizard.arcane_recovery', cls: 'wizard', keyPrefix: 'arcane_recovery', testId: 'arcane-recovery', idPrefix: 'ar' }

interface PickerProps {
  char: CharacterFull
  value: Record<number, number>
  onChange: (next: Record<number, number>) => void
}

/** Recupero Naturale (Druido 2014, Circolo della Terra) nel foglio del riposo breve: quali slot spesi riprendere. Il server
 *  ricontrolla tutto (tetto, slot davvero spesi, un solo uso) e rifiuta il riposo intero se qualcosa non torna. */
export default function NaturalRecoveryPicker(props: PickerProps) {
  return <SlotRecoveryPicker {...props} kind={NATURAL} />
}

/** Recupero Arcano (Mago 2014): stesso foglio, tetto dal livello da mago. */
export function ArcaneRecoveryPicker(props: PickerProps) {
  return <SlotRecoveryPicker {...props} kind={ARCANE} />
}

function SlotRecoveryPicker({ char, value, onChange, kind }: PickerProps & { kind: RecoveryKind }) {
  const { t } = useTranslation()
  const ability = (char.abilities ?? []).find((a) => a.feature_key === kind.feature)
  const classLevel = (char.classes ?? []).filter((c) => classKey(c.class_name) === kind.cls).reduce((n, c) => n + c.level, 0)
  const spent = (char.spell_slots ?? []).filter((s) => !s.is_pact && s.level <= MAX_LEVEL && s.used > 0)
  if (!ability || (ability.max_uses != null && (ability.uses ?? 0) < 1) || classLevel < 1 || spent.length === 0) return null

  const used = Object.entries(value).reduce((n, [lv, count]) => n + Number(lv) * count, 0)
  const left = recoveryBudget(classLevel) - used
  const set = (level: number, count: number) => {
    const next = { ...value, [level]: count }
    if (count <= 0) delete next[level]
    onChange(next)
  }

  return (
    <section data-testid={kind.testId} className="space-y-2 text-left">
      <h3 className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim">{t(`character.quick_actions.${kind.keyPrefix}`)}</h3>
      <p className="text-sm font-body text-dnd-text">
        {t(`character.quick_actions.${kind.keyPrefix}_hint`)}{' '}
        <span data-testid={`${kind.idPrefix}-left`} className="font-mono tabular-nums font-bold">{left}</span>
      </p>
      <ul className="space-y-1.5">
        {spent.map((s) => {
          const count = value[s.level] ?? 0
          return (
            <li key={s.level} className="flex items-center gap-2">
              <span className="flex-1 text-sm font-body text-dnd-text">
                {t(`character.quick_actions.${kind.keyPrefix}_slot`, { level: s.level, spent: s.used })}
              </span>
              <span data-testid={`${kind.idPrefix}-minus-${s.level}`}>
                <IconButton variant="secondary" className="min-h-11 min-w-11" icon={<Minus size={16} />} disabled={count === 0}
                  aria-label={t(`character.quick_actions.${kind.keyPrefix}_less`, { level: s.level })} onClick={() => set(s.level, count - 1)} />
              </span>
              <span data-testid={`${kind.idPrefix}-count-${s.level}`} className="w-6 text-center font-mono tabular-nums font-bold">{count}</span>
              <span data-testid={`${kind.idPrefix}-plus-${s.level}`}>
                <IconButton variant="secondary" className="min-h-11 min-w-11" icon={<Plus size={16} />} disabled={count >= s.used || s.level > left}
                  aria-label={t(`character.quick_actions.${kind.keyPrefix}_more`, { level: s.level })} onClick={() => set(s.level, count + 1)} />
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

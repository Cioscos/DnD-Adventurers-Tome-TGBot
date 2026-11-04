import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import Pressable from '@/components/ui/Pressable'
import { haptic } from '@/auth/telegram'
import { LEDGER_LABEL, LEDGER_ROW } from '@/styles/ledger'
import type { SpellSlot } from '@/types'

interface Props {
  slots: SpellSlot[]
}

export default function SpellSlotsSummary({ slots }: Props) {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation()

  // Sum across rows per level so a Warlock multiclass (separate regular + pact
  // rows at the same spell level) shows the combined castable count — the two
  // pools are interchangeable.
  const byLevel = new Map<number, { available: number; total: number }>()
  for (const s of slots ?? []) {
    const cell = byLevel.get(s.level) ?? { available: 0, total: 0 }
    byLevel.set(s.level, { available: cell.available + s.available, total: cell.total + s.total })
  }
  const cells = [...byLevel.entries()]
    .filter(([, c]) => c.total > 0)
    .sort(([a], [b]) => a - b)

  if (cells.length === 0) return null

  const label = t('character.equipment.summary.spell_slots', { defaultValue: 'Spell slots' })
  return (
    <Pressable
      type="button"
      onClick={() => {
        haptic.light()
        navigate(`/char/${id}/slots`)
      }}
      whileTap={{ scale: 0.99 }}
      className={`${LEDGER_ROW} border-y border-dnd-border`}
      aria-label={label}
    >
      <span className={`shrink-0 ${LEDGER_LABEL}`}>{label}</span>
      <span className="flex flex-wrap justify-end gap-x-3 gap-y-1">
        {cells.map(([level, c]) => (
          <span key={level} className="whitespace-nowrap">
            <span className="font-mono text-xs text-dnd-text-muted">{level}°</span>{' '}
            <span className={`font-mono text-sm font-bold tabular-nums ${c.available === 0 ? 'text-dnd-text-faint' : 'text-dnd-gold-bright'}`}>
              {c.available}
            </span>
            <span className="font-mono text-xs tabular-nums text-dnd-text-muted">/{c.total}</span>
          </span>
        ))}
      </span>
    </Pressable>
  )
}

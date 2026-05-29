import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import Surface from '@/components/ui/Surface'
import { haptic } from '@/auth/telegram'
import type { SpellSlot } from '@/types'

interface Props {
  slots: SpellSlot[]
}

export default function SpellSlotsSummary({ slots }: Props) {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { t } = useTranslation()

  if (!slots || slots.length === 0) return null

  // Build a fixed 9-column display (level 1..9). Sum across rows per level so a
  // Warlock multiclass (separate regular + pact rows at the same spell level)
  // shows the combined castable count — the two pools are interchangeable.
  const byLevel = new Map<number, number>()
  for (const s of slots) byLevel.set(s.level, (byLevel.get(s.level) ?? 0) + s.total)
  const cells = [1, 2, 3, 4, 5, 6, 7, 8, 9].map((lv) => ({
    level: lv,
    total: byLevel.get(lv) ?? 0,
  }))

  // Hide entirely if every level has zero slots.
  if (cells.every((c) => c.total === 0)) return null

  return (
    <Surface variant="tome" className="@container !p-2.5">
      <m.button
        type="button"
        onClick={() => {
          haptic.light()
          navigate(`/char/${id}/slots`)
        }}
        whileTap={{ scale: 0.99 }}
        className="w-full text-left"
        aria-label={t('character.equipment.summary.spell_slots', { defaultValue: 'Spell slots' })}
      >
        <div className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim mb-1">
          {t('character.equipment.summary.spell_slots', { defaultValue: 'Spell slots' })}
        </div>
        <div className="grid grid-cols-9 gap-1 @max-[300px]:gap-0.5 text-center font-mono text-dnd-text">
          {cells.map((c) => (
            <div key={c.level} className="flex flex-col">
              <span className="text-[9px] @max-[300px]:text-[8px] text-dnd-gold-dim">{c.level}</span>
              <span className={`@max-[300px]:text-[11px] ${c.total === 0 ? 'text-dnd-text-muted' : 'text-dnd-gold-bright font-bold'}`}>
                {c.total}
              </span>
            </div>
          ))}
        </div>
      </m.button>
    </Surface>
  )
}

import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import Surface from '@/components/ui/Surface'
import Pressable from '@/components/ui/Pressable'
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

  // Griglia fissa di 9 colonne (livelli 1..9). Somma le righe per livello così un
  // multiclasse Warlock (righe normali + patto allo stesso livello) mostra il
  // totale lanciabile: i due gruppi sono intercambiabili.
  const byLevel = new Map<number, { available: number; total: number }>()
  for (const s of slots) {
    const cell = byLevel.get(s.level) ?? { available: 0, total: 0 }
    byLevel.set(s.level, { available: cell.available + s.available, total: cell.total + s.total })
  }
  const cells = [1, 2, 3, 4, 5, 6, 7, 8, 9].map((level) => ({
    level,
    available: byLevel.get(level)?.available ?? 0,
    total: byLevel.get(level)?.total ?? 0,
  }))

  if (cells.every((c) => c.total === 0)) return null

  const label = t('character.equipment.summary.spell_slots', { defaultValue: 'Spell slots' })
  return (
    <Surface variant="tome" className="@container !p-2.5">
      <Pressable
        type="button"
        onClick={() => {
          haptic.light()
          navigate(`/char/${id}/slots`)
        }}
        whileTap={{ scale: 0.99 }}
        className="w-full text-left"
        aria-label={label}
      >
        <div className="text-xs font-cinzel uppercase tracking-widest text-dnd-gold-dim mb-1">
          {label}
        </div>
        <div className="grid grid-cols-9 gap-1 @max-[300px]:gap-0.5 text-center font-mono text-dnd-text">
          {cells.map((c) => (
            <div key={c.level} className="flex flex-col">
              <span className="text-xs text-dnd-gold-dim">{c.level}</span>
              {/* 0 = finiti, trattino = livello che il personaggio non ha. */}
              <span className={`@max-[300px]:text-xs ${c.total === 0 ? 'text-dnd-text-muted' : c.available === 0 ? 'text-dnd-text font-bold' : 'text-dnd-gold-bright font-bold'}`}>
                {c.total === 0 ? '–' : c.available}
              </span>
            </div>
          ))}
        </div>
      </Pressable>
    </Surface>
  )
}

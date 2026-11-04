import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import Pressable from '@/components/ui/Pressable'
import { haptic } from '@/auth/telegram'
import { LEDGER_LABEL } from '@/styles/ledger'
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
    <Pressable
      type="button"
      onClick={() => {
        haptic.light()
        navigate(`/char/${id}/slots`)
      }}
      whileTap={{ scale: 0.99 }}
      className="@container block w-full border-y border-dnd-border px-1 py-2 text-left hover:bg-dnd-surface/60 transition-colors"
      aria-label={label}
    >
      <div className={`mb-1.5 ${LEDGER_LABEL}`}>{label}</div>
      <div className="grid grid-cols-9 divide-x divide-dnd-border/60 text-center font-mono tabular-nums">
        {cells.map((c) => (
          <div key={c.level} className="flex flex-col">
            <span className="text-xs text-dnd-text-muted">{c.level}</span>
            {/* 0 = finiti, trattino = livello che il personaggio non ha. */}
            <span className={`@max-[300px]:text-xs ${c.total === 0 ? 'text-dnd-text-muted' : c.available === 0 ? 'text-dnd-text font-bold' : 'text-dnd-gold-bright font-bold'}`}>
              {c.total === 0 ? '–' : c.available}
            </span>
          </div>
        ))}
      </div>
    </Pressable>
  )
}

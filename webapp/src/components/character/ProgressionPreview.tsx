import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import Surface from '@/components/ui/Surface'
import progressionData from '@/data/class-progression.json'
import ProgressionFullTableModal from './ProgressionFullTableModal'

interface ProgressionRow {
  features: string
  proficiency_bonus: number
  spell_slots: number[] | null
}

const PROGRESSION = progressionData as unknown as Record<string, ProgressionRow[]>

interface Props {
  className: string
  currentLevel: number
}

function computeWindow(currentLevel: number, max: number): number[] {
  // 5-row window: try [current-1 .. current+3], clamp to [1..max]
  const start = Math.max(1, Math.min(currentLevel - 1, max - 4))
  return [0, 1, 2, 3, 4].map((i) => start + i).filter((lv) => lv <= max)
}

export default function ProgressionPreview({ className, currentLevel }: Props) {
  const { t } = useTranslation()
  const [showFull, setShowFull] = useState(false)

  const rows = PROGRESSION[className]
  const windowLevels = useMemo(
    () => computeWindow(currentLevel, rows?.length ?? 20),
    [currentLevel, rows?.length],
  )

  if (!rows) {
    return (
      <Surface variant="tome" className="!p-3">
        <p className="text-xs text-dnd-text-faint italic">
          {t('character.equipment.progression.no_data', {
            className,
            defaultValue: `Progression data not available for ${className}`,
          })}
        </p>
      </Surface>
    )
  }

  return (
    <>
      <Surface variant="tome" className="!p-2.5">
        <div className="flex items-center justify-between mb-1.5">
          <div className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim">
            {t('character.equipment.progression.title', { defaultValue: 'Progression' })}
          </div>
          <div className="text-[9px] text-dnd-text-faint italic">
            {t('character.equipment.progression.tap_full_table', {
              defaultValue: 'Tap row for full table',
            })}
          </div>
        </div>
        <div className="space-y-0.5">
          {windowLevels.map((lv) => {
            const row = rows[lv - 1]
            const isCurrent = lv === currentLevel
            return (
              <m.button
                key={lv}
                type="button"
                onClick={() => setShowFull(true)}
                whileTap={{ scale: 0.99 }}
                className={`w-full grid grid-cols-[28px_36px_1fr] gap-2 items-center rounded-md px-1.5 py-1 text-left transition-colors ${
                  isCurrent
                    ? 'bg-dnd-gold/15 border border-dnd-gold text-dnd-gold-bright'
                    : 'border border-transparent text-dnd-text-muted hover:bg-dnd-surface'
                }`}
                aria-current={isCurrent ? 'true' : undefined}
              >
                <span className="font-mono text-[11px] font-bold text-center">L{lv}</span>
                <span className="font-mono text-[10px] text-center">+{row?.proficiency_bonus ?? '?'}</span>
                <span className="text-[11px] truncate">{row?.features ?? '—'}</span>
              </m.button>
            )
          })}
        </div>
      </Surface>
      {showFull && (
        <ProgressionFullTableModal
          className={className}
          currentLevel={currentLevel}
          onClose={() => setShowFull(false)}
        />
      )}
    </>
  )
}

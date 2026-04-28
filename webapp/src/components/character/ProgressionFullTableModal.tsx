import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'
import progressionData from '@/data/class-progression.json'

interface ProgressionRow {
  features: string
  proficiency_bonus: number
  spell_slots: number[] | null
}

const PROGRESSION = progressionData as unknown as Record<string, ProgressionRow[]>

interface Props {
  className: string
  currentLevel: number
  onClose: () => void
}

export default function ProgressionFullTableModal({ className, currentLevel, onClose }: Props) {
  const { t } = useTranslation()
  const currentRowRef = useRef<HTMLTableRowElement>(null)
  const rows = PROGRESSION[className] ?? []

  useEffect(() => {
    currentRowRef.current?.scrollIntoView({ behavior: 'auto', block: 'center' })
  }, [])

  return (
    <AnimatePresence>
      <m.div
        className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/70 backdrop-blur-sm"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <m.div
          className="w-full max-w-md max-h-[85vh] overflow-y-auto bg-dnd-surface-raised border border-dnd-gold rounded-t-2xl sm:rounded-2xl"
          initial={{ y: 40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 40, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
        >
          <header className="sticky top-0 z-10 flex items-center justify-between px-4 py-3 bg-dnd-surface-raised border-b border-dnd-gold-dim/40">
            <h2 className="text-sm font-cinzel uppercase tracking-widest text-dnd-gold-bright">
              {className} — {t('character.equipment.progression.title', { defaultValue: 'Progression' })}
            </h2>
            <button
              type="button"
              onClick={onClose}
              aria-label={t('common.close', { defaultValue: 'Close' })}
              className="w-8 h-8 flex items-center justify-center rounded-full border border-dnd-gold-dim/40"
            >
              <X size={16} className="text-dnd-gold" />
            </button>
          </header>
          <table className="w-full text-left text-[12px]">
            <thead className="text-[10px] uppercase tracking-wider text-dnd-gold-dim sticky top-12 bg-dnd-surface-raised">
              <tr>
                <th className="px-3 py-2 w-12">Lv</th>
                <th className="px-2 py-2 w-12">PB</th>
                <th className="px-3 py-2">Features</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const lv = i + 1
                const isCurrent = lv === currentLevel
                return (
                  <tr
                    key={lv}
                    ref={isCurrent ? currentRowRef : undefined}
                    className={
                      isCurrent
                        ? 'bg-dnd-gold/15 text-dnd-gold-bright'
                        : 'text-dnd-text-muted border-t border-dnd-gold-dim/10'
                    }
                  >
                    <td className="px-3 py-2 font-mono font-bold">L{lv}</td>
                    <td className="px-2 py-2 font-mono">+{r.proficiency_bonus}</td>
                    <td className="px-3 py-2">{r.features}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </m.div>
      </m.div>
    </AnimatePresence>
  )
}

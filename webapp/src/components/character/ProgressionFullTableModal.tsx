import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'
import { progressionRows } from '@/lib/classProgression'

interface Props {
  className: string
  currentLevel: number
  onClose: () => void
}

export default function ProgressionFullTableModal({ className, currentLevel, onClose }: Props) {
  const { t } = useTranslation()
  const currentRowRef = useRef<HTMLTableRowElement>(null)
  const rows = progressionRows(className) ?? []

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
          className="w-full max-w-md max-h-[85vh] flex flex-col bg-dnd-surface-raised border border-dnd-gold rounded-t-2xl sm:rounded-2xl overflow-hidden"
          initial={{ y: 40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 40, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
        >
          <header className="flex-shrink-0 flex items-center justify-between px-4 py-3 bg-dnd-surface-raised border-b border-dnd-gold-dim/40">
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
          <div className="flex-1 overflow-y-auto">
            <table className="w-full text-left text-[12px] table-fixed">
              <thead className="text-[10px] uppercase tracking-wider text-dnd-gold-dim sticky top-0 bg-dnd-surface-raised">
                <tr>
                  <th className="px-2 py-2 w-10">Lv</th>
                  <th className="px-2 py-2 w-10">PB</th>
                  <th className="px-2 py-2">Features</th>
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
                      <td className="px-2 py-2 font-mono font-bold">L{lv}</td>
                      <td className="px-2 py-2 font-mono">+{r.proficiency_bonus}</td>
                      <td className="px-2 py-2 break-words">{r.features}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </m.div>
      </m.div>
    </AnimatePresence>
  )
}

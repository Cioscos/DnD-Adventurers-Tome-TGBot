import { useTranslation } from 'react-i18next'
import Pressable from '@/components/ui/Pressable'
import type { RollMode } from '@/api/client'

const MODES: RollMode[] = ['normal', 'advantage', 'disadvantage']

/** Normale / Vantaggio / Svantaggio in tre pulsanti: per i tiri che si preparano prima (TS di una condizione, concentrazione). */
export default function RollModeToggle({ mode, onChange, label }: {
  mode: RollMode
  onChange: (mode: RollMode) => void
  label?: string
}) {
  const { t } = useTranslation()
  return (
    <div role="radiogroup" aria-label={label ?? t('common.roll_mode.title')} className="grid grid-cols-3 gap-2">
      {MODES.map((md) => (
        <Pressable
          key={md}
          role="radio"
          aria-checked={mode === md}
          haptic="light"
          onClick={() => onChange(md)}
          whileTap={{ scale: 0.95 }}
          className={`min-h-[44px] rounded-xl border text-sm font-body ${
            mode === md
              ? 'border-dnd-gold bg-dnd-gold/20 text-dnd-gold-bright font-semibold'
              : 'border-dnd-gold-dim/30 bg-dnd-surface text-dnd-text-muted'
          }`}
        >
          {t(`common.roll_mode.${md}`)}
        </Pressable>
      ))}
    </div>
  )
}

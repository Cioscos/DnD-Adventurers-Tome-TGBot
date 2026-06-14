import { Sparkles } from 'lucide-react'
import { useTranslation } from 'react-i18next'

interface Props {
  value: number
  label?: string
  /** Overrides the default `+{value}` rendering (e.g. a unit-formatted speed delta). */
  display?: string
}

export default function HomebrewBreakdownRow({ value, label, display }: Props) {
  const { t } = useTranslation()

  if (value === 0) return null

  const text = label ?? t('homebrew.breakdown.label')

  return (
    <div className="flex items-center justify-between gap-2 px-2 py-1 text-sm">
      <span className="flex items-center gap-1.5 text-[10px] font-cinzel uppercase tracking-[0.3em] text-dnd-gold-dim">
        <Sparkles size={14} className="text-dnd-gold-dim" />
        {text}
      </span>
      <span className="font-mono font-bold tabular-nums text-dnd-gold-bright">
        {display ?? `+${value}`}
      </span>
    </div>
  )
}

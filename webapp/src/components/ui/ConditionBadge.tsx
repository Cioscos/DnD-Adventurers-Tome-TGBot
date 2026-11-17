import { useTranslation } from 'react-i18next'
import { CircleDot } from 'lucide-react'
import { CONDITION_ICONS, formatCondition } from '@/lib/conditions'
import Tooltip from '@/components/ui/Tooltip'

interface ConditionBadgeProps {
  conditionKey: string
  value: unknown
  size?: 'sm' | 'md'
  /** Tracker: nome scritto accanto all'icona, con un dettaglio breve (durata). */
  showLabel?: boolean
  detail?: string
  /** Righe in più nel tooltip (scadenza, TS ripetuto, fonte). */
  notes?: string[]
}

export default function ConditionBadge({
  conditionKey, value, size = 'sm', showLabel = false, detail, notes = [],
}: ConditionBadgeProps) {
  const { t } = useTranslation()
  const Icon = CONDITION_ICONS[conditionKey] ?? CircleDot
  const label = formatCondition(conditionKey, value, t)
  const description = t(`character.conditions.desc.${conditionKey}`, { defaultValue: '' })

  const dimPx = size === 'md' ? 28 : 24
  const iconPx = size === 'md' ? 16 : 14

  return (
    <Tooltip
      content={
        <>
          <p className="font-display font-bold text-dnd-amber mb-1">{label}</p>
          {notes.map((n) => <p key={n} className="text-dnd-text mb-1">{n}</p>)}
          {description && <p className="text-dnd-text-muted">{description}</p>}
        </>
      }
    >
      <button
        type="button"
        aria-label={label}
        className={`hit-44 inline-flex items-center rounded-full bg-dnd-surface
                   border border-dnd-amber/70 text-dnd-amber transition-colors
                   hover:border-dnd-amber active:scale-95
                   ${showLabel ? 'gap-1 px-2 text-xs font-body whitespace-nowrap' : 'justify-center'}`}
        style={showLabel ? { height: dimPx } : { width: dimPx, height: dimPx }}
      >
        <Icon size={iconPx} className="shrink-0" />
        {showLabel && (
          <span>
            {label}
            {detail && <span className="tabular-nums text-dnd-text-muted"> · {detail}</span>}
          </span>
        )}
      </button>
    </Tooltip>
  )
}

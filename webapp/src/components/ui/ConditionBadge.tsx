import { useTranslation } from 'react-i18next'
import { CircleDot } from 'lucide-react'
import { CONDITION_ICONS, formatCondition } from '@/lib/conditions'
import Tooltip from '@/components/ui/Tooltip'

interface ConditionBadgeProps {
  conditionKey: string
  value: unknown
  size?: 'sm' | 'md'
}

export default function ConditionBadge({ conditionKey, value, size = 'sm' }: ConditionBadgeProps) {
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
          {description && <p className="text-dnd-text-muted">{description}</p>}
        </>
      }
    >
      <button
        type="button"
        aria-label={label}
        className="inline-flex items-center justify-center rounded-full bg-dnd-surface
                   border border-dnd-amber/70 text-dnd-amber transition-colors
                   hover:border-dnd-amber active:scale-95"
        style={{ width: dimPx, height: dimPx }}
      >
        <Icon size={iconPx} />
      </button>
    </Tooltip>
  )
}

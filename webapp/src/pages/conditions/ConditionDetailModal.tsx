import { useTranslation } from 'react-i18next'
import DndButton from '@/components/DndButton'

interface ConditionDetailModalProps {
  condKey: string
  exhaustionLevel?: number
  onClose: () => void
}

export default function ConditionDetailModal({
  condKey,
  exhaustionLevel = 0,
  onClose,
}: ConditionDetailModalProps) {
  const { t } = useTranslation()
  const isExhaustion = condKey === 'exhaustion'

  const title = isExhaustion
    ? (exhaustionLevel > 0
        ? t('character.conditions.exhaustion', { level: exhaustionLevel })
        : t('character.conditions.exhaustion_condition'))
    : t(`character.conditions.${condKey}`)

  const description = t(`character.conditions.desc.${condKey}`)

  const levels = isExhaustion
    ? (t('character.conditions.desc.exhaustion_levels', {
        returnObjects: true,
      }) as string[])
    : []

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-end z-50 p-4"
      onClick={onClose}
    >
      <div
        className="w-full rounded-2xl bg-dnd-surface-elevated p-4 space-y-3"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h3 className="font-semibold font-cinzel text-dnd-gold">{title}</h3>
          <button
            onClick={onClose}
            aria-label={t('common.close')}
            className="text-dnd-text-secondary text-sm p-1"
          >
            &#x2715;
          </button>
        </div>
        <p className="text-sm text-dnd-text font-body leading-relaxed whitespace-pre-line">
          {description}
        </p>
        {isExhaustion && levels.length > 0 && (
          <ol className="space-y-1 text-sm font-body list-none pl-0">
            {levels.map((line, i) => (
              <li
                key={i}
                className="pl-2 border-l-2 border-dnd-gold/40 text-dnd-text-muted"
              >
                {line}
              </li>
            ))}
          </ol>
        )}
        <DndButton variant="secondary" onClick={onClose} className="w-full">
          {t('common.close')}
        </DndButton>
      </div>
    </div>
  )
}

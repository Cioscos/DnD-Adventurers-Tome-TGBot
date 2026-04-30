import { useEffect } from 'react'
import { createPortal } from 'react-dom'
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

  useEffect(() => {
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previous
    }
  }, [])

  return createPortal(
    <div
      className="fixed inset-0 bg-dnd-overlay flex items-end z-50 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="w-full max-w-md mx-auto rounded-2xl bg-dnd-surface-elevated border border-dnd-gold-dim/40 p-4 space-y-3"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h3 className="font-semibold font-cinzel text-dnd-gold">{title}</h3>
          <button
            onClick={onClose}
            aria-label={t('common.close')}
            className="text-dnd-text-muted text-sm p-1"
          >
            &#x2715;
          </button>
        </div>
        <p className="text-sm text-dnd-text font-body leading-relaxed whitespace-pre-line">
          {description}
        </p>
        {isExhaustion && levels.length > 0 && (
          <ol className="space-y-1.5 text-sm font-body list-none pl-0">
            {levels.map((line, i) => (
              <li
                key={i}
                className="rounded-md px-2 py-1 bg-dnd-gold/10 text-dnd-text-muted"
              >
                <span className="font-mono font-bold text-dnd-gold-bright mr-2">L{i + 1}</span>
                {line}
              </li>
            ))}
          </ol>
        )}
        <DndButton variant="secondary" onClick={onClose} className="w-full">
          {t('common.close')}
        </DndButton>
      </div>
    </div>,
    document.body,
  )
}

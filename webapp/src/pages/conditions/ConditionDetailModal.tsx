import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'

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
    <Sheet open onClose={onClose} title={title} centered>
      <div className="p-5 space-y-3">
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
        <Button variant="secondary" fullWidth onClick={onClose}>
          {t('common.close')}
        </Button>
      </div>
    </Sheet>
  )
}

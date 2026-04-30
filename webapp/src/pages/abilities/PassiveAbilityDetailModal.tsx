import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import type { Ability } from '@/types'

interface PassiveAbilityDetailModalProps {
  ability: Ability
  onClose: () => void
}

export default function PassiveAbilityDetailModal({
  ability,
  onClose,
}: PassiveAbilityDetailModalProps) {
  const { t } = useTranslation()

  return (
    <Sheet open onClose={onClose} title={ability.name} centered>
      <div className="p-5 space-y-4">
        {ability.description ? (
          <p className="text-sm text-dnd-text font-body leading-relaxed whitespace-pre-line">
            {ability.description}
          </p>
        ) : (
          <p className="text-sm italic text-dnd-text-muted font-body">
            {t('character.abilities.detail.no_description')}
          </p>
        )}
        <Button variant="secondary" fullWidth onClick={onClose}>
          {t('common.close')}
        </Button>
      </div>
    </Sheet>
  )
}

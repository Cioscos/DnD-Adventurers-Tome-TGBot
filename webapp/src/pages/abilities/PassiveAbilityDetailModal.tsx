import { useTranslation } from 'react-i18next'
import DndButton from '@/components/DndButton'
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
    <div
      className="fixed inset-0 bg-black/60 flex items-end z-50 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="passive-ability-title"
    >
      <div
        className="w-full rounded-2xl bg-dnd-surface-elevated p-4 space-y-3"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h3 id="passive-ability-title" className="font-semibold font-cinzel text-dnd-gold">
            {ability.name}
          </h3>
          <button
            onClick={onClose}
            aria-label={t('common.close')}
            className="text-dnd-text-secondary text-sm p-1"
          >
            &#x2715;
          </button>
        </div>
        {ability.description ? (
          <p className="text-sm text-dnd-text font-body leading-relaxed whitespace-pre-line">
            {ability.description}
          </p>
        ) : (
          <p className="text-sm italic text-dnd-text-faint font-body">
            {t('character.abilities.detail.no_description')}
          </p>
        )}
        <DndButton variant="secondary" onClick={onClose} className="w-full">
          {t('common.close')}
        </DndButton>
      </div>
    </div>
  )
}

import { useEffect } from 'react'
import { createPortal } from 'react-dom'
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
      aria-labelledby="passive-ability-title"
    >
      <div
        className="w-full max-w-md mx-auto rounded-2xl bg-dnd-surface-elevated border border-dnd-gold-dim/40 p-4 space-y-3"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h3 id="passive-ability-title" className="font-semibold font-cinzel text-dnd-gold">
            {ability.name}
          </h3>
          <button
            onClick={onClose}
            aria-label={t('common.close')}
            className="text-dnd-text-muted text-sm p-1"
          >
            &#x2715;
          </button>
        </div>
        {ability.description ? (
          <p className="text-sm text-dnd-text font-body leading-relaxed whitespace-pre-line">
            {ability.description}
          </p>
        ) : (
          <p className="text-sm italic text-dnd-text-muted font-body">
            {t('character.abilities.detail.no_description')}
          </p>
        )}
        <DndButton variant="secondary" onClick={onClose} className="w-full">
          {t('common.close')}
        </DndButton>
      </div>
    </div>,
    document.body,
  )
}

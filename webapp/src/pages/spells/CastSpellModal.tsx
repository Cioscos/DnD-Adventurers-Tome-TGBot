import { useTranslation } from 'react-i18next'
import DndButton from '@/components/DndButton'
import type { Spell, SpellSlot } from '@/types'

interface CastSpellModalProps {
  spell: Spell
  availableSlots: SpellSlot[]
  onCast: (slotLevel: number) => void
  onCancel: () => void
  isPending: boolean
}

export default function CastSpellModal({
  spell,
  availableSlots,
  onCast,
  onCancel,
  isPending,
}: CastSpellModalProps) {
  const { t } = useTranslation()

  return (
    <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4">
      <div className="w-full rounded-2xl bg-dnd-surface-elevated p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold font-cinzel text-dnd-gold">{t('character.spells.cast_slot_title')}</h3>
          <button onClick={onCancel} className="text-dnd-text-secondary text-sm">
            &#x2715;
          </button>
        </div>
        <p className="text-sm text-dnd-text-secondary">{spell.name}</p>
        <div className="space-y-2">
          {availableSlots.length === 0 ? (
            <p className="text-sm text-[var(--dnd-danger)] text-center py-2">{t('character.spells.no_slots')}</p>
          ) : (
            availableSlots.map((slot) => (
              <DndButton
                key={slot.id}
                variant="secondary"
                onClick={() => onCast(slot.level)}
                disabled={isPending}
                className="w-full"
              >
                {t('character.slots.level', { level: slot.level })} — {slot.available}/{slot.total}
              </DndButton>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

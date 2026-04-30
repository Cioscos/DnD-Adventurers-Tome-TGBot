import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
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
    <Sheet open onClose={onCancel} title={t('character.spells.cast_slot_title')}>
      <div className="p-5 space-y-3">
        <p className="text-sm text-dnd-text-muted font-body italic">{spell.name}</p>
        <div className="space-y-2">
          {availableSlots.length === 0 ? (
            <p className="text-sm text-dnd-crimson-bright text-center py-4 font-body">
              {t('character.spells.no_slots')}
            </p>
          ) : (
            availableSlots.map((slot) => (
              <Button
                key={slot.id}
                variant="secondary"
                fullWidth
                onClick={() => onCast(slot.level)}
                disabled={isPending}
              >
                {t('character.slots.level', { level: slot.level })} — {slot.available}/{slot.total}
              </Button>
            ))
          )}
        </div>
        <Button variant="ghost" fullWidth onClick={onCancel}>
          {t('common.cancel')}
        </Button>
      </div>
    </Sheet>
  )
}

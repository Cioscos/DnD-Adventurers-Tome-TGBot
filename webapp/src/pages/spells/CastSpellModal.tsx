import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Sparkles } from 'lucide-react'
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
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()

  return (
    <Sheet open onClose={onCancel} title={t('character.spells.cast_slot_title')}>
      <div className="p-5 space-y-3">
        <p className="text-sm text-dnd-text-muted font-body italic">{spell.name}</p>
        <div className="space-y-2">
          {availableSlots.length === 0 ? (
            <div className="space-y-3 py-2">
              <p className="text-sm text-dnd-crimson-bright text-center font-body">
                {t('character.spells.no_slots')}
              </p>
              <Button
                variant="secondary"
                fullWidth
                icon={<Sparkles size={14} />}
                onClick={() => { onCancel(); navigate(`/char/${id}/slots`) }}
              >
                {t('character.spells.go_create_slot', {
                  level: spell.level,
                  defaultValue: 'Crea slot livello {{level}}',
                })}
              </Button>
            </div>
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

import { useTranslation } from 'react-i18next'
import { Sparkles, BookOpen } from 'lucide-react'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import type { Spell, SpellSlot } from '@/types'

interface CastSpellModalProps {
  spell: Spell
  availableSlots: SpellSlot[]
  /** True se l'incantesimo è rituale E il PG ha una classe con Ritual Casting. */
  canRitual: boolean
  onCast: (slotLevel: number) => void
  onCastRitual: () => void
  onCreateSlot: (level: number) => void
  onCancel: () => void
  isPending: boolean
  isCreatingSlot: boolean
}

export default function CastSpellModal({
  spell,
  availableSlots,
  canRitual,
  onCast,
  onCastRitual,
  onCreateSlot,
  onCancel,
  isPending,
  isCreatingSlot,
}: CastSpellModalProps) {
  const { t } = useTranslation()

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
                onClick={() => onCreateSlot(spell.level)}
                disabled={isCreatingSlot}
                loading={isCreatingSlot}
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
                {t('character.slots.level', { level: slot.level })} · <span className="font-mono tabular-nums">{slot.available}/{slot.total}</span>
              </Button>
            ))
          )}
        </div>
        {/* Rituale: visibile anche a slot esauriti, un rituale non li richiede. */}
        {canRitual && (
          <div className="pt-3 border-t border-dnd-border/60 space-y-2">
            <p className="text-xs text-dnd-text-muted font-body italic text-center">
              {t('character.spells.ritual_hint')}
            </p>
            <Button
              variant="secondary"
              fullWidth
              icon={<BookOpen size={14} />}
              onClick={onCastRitual}
              disabled={isPending}
            >
              {t('character.spells.cast_ritual')}
            </Button>
          </div>
        )}
        <Button variant="ghost" fullWidth onClick={onCancel}>
          {t('common.cancel')}
        </Button>
      </div>
    </Sheet>
  )
}

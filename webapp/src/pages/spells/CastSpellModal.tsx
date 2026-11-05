import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Sparkles, BookOpen } from 'lucide-react'
import Button from '@/components/ui/Button'
import AmountStepper from '@/components/rules/AmountStepper'
import type { Spell, SpellSlot } from '@/types'

interface CastSpellModalProps {
  spell: Spell
  availableSlots: SpellSlot[]
  /** True se l'incantesimo è rituale E il PG ha una classe con Ritual Casting. */
  canRitual: boolean
  onCast: (slot: SpellSlot) => void
  onCastRitual: () => void
  /** Autorizzato da uno stato attivo (Lettura del Pensiero): costa l'azione, non uno slot. */
  canFreeCast?: boolean
  onCastFree?: () => void
  /** Si lancia anche coi punti ki (Arti dell'Ombra, discipline): `extra` ki in più alzano il livello. */
  kiCast?: Spell['ki_cast']
  onCastKi?: (extra: number) => void
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
  canFreeCast = false,
  onCastFree,
  kiCast = null,
  onCastKi,
  onCreateSlot,
  onCancel,
  isPending,
  isCreatingSlot,
}: CastSpellModalProps) {
  const { t } = useTranslation()
  const [kiExtra, setKiExtra] = useState(0)
  const kiAffordable = !!kiCast && kiCast.ki_left >= kiCast.cost

  // Corpo del primo passo dello sheet di lancio (lo sheet lo monta useCastFlow).
  return (
      <div className="p-5 space-y-3">
        <p className="text-sm text-dnd-text-muted font-body italic">{spell.name}</p>
        <div className="space-y-2">
          {availableSlots.length === 0 && kiCast ? null : availableSlots.length === 0 ? (
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
                onClick={() => onCast(slot)}
                disabled={isPending}
              >
                <span className="flex-1 text-left">
                  {t('character.slots.level', { level: slot.level })}
                  {slot.is_pact && ` · ${t('character.slots.pact_badge')}`}
                </span>
                {/* Stessa convenzione dei pallini nella pagina Incantesimi: dorato = usato. */}
                <span className="flex gap-1" aria-hidden>
                  {Array.from({ length: slot.total }).map((_, i) => (
                    <span key={i} className={`w-3 h-3 rounded-full border ${i < slot.used
                      ? 'bg-dnd-gold border-dnd-gold-bright'
                      : 'border-dnd-gold-dim/70'}`} />
                  ))}
                </span>
                <span className="text-xs font-normal text-dnd-text-muted tabular-nums">
                  {t('character.slots.available_count', { count: slot.available })}
                </span>
              </Button>
            ))
          )}
        </div>
        {kiCast && (
          <div className={`space-y-2 ${availableSlots.length > 0 ? 'pt-3 border-t border-dnd-border/60' : ''}`}>
            <p className="text-xs text-dnd-text-muted font-body italic text-center">
              {t('character.spells.cast_ki_hint', { left: kiCast.ki_left })}
            </p>
            {kiCast.max_extra > 0 && (
              <AmountStepper value={kiExtra} min={0} max={kiCast.max_extra} label={t('character.spells.cast_ki_extra')} onChange={setKiExtra} />
            )}
            <Button variant="secondary" fullWidth icon={<Sparkles size={14} />} onClick={() => onCastKi?.(kiExtra)}
              disabled={isPending || !kiAffordable}>
              {t('character.spells.cast_ki', { cost: kiCast.cost + kiExtra })}
            </Button>
            {!kiAffordable && <p className="text-xs text-dnd-crimson-bright font-body text-center">{t('character.spells.cast_ki_none')}</p>}
          </div>
        )}
        {canFreeCast && (
          <div className="pt-3 border-t border-dnd-border/60 space-y-2">
            <p className="text-xs text-dnd-text-muted font-body italic text-center">{t('character.spells.free_cast_hint')}</p>
            <Button variant="secondary" fullWidth icon={<Sparkles size={14} />} onClick={onCastFree} disabled={isPending}>
              {t('character.spells.cast_free')}
            </Button>
          </div>
        )}
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
  )
}

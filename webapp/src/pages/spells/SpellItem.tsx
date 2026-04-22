import React from 'react'
import { useTranslation } from 'react-i18next'
import {
  Clock, Crosshair, FlaskConical, Timer,
  Swords, Shield, Pencil, Trash2, Sparkles, Ban, Dices,
} from 'lucide-react'
import type { Spell } from '@/types'

interface SpellItemProps {
  spell: Spell
  isExpanded: boolean
  onToggle: () => void
  onCast: () => void
  onCastCantrip: () => void
  onConcentrationToggle: () => void
  onEdit: () => void
  onRemove: () => void
  concentratingSpellId: number | null
  castCantripPending: boolean
  onRollDamage?: (spell: Spell) => void
}

function SpellItemInner({
  spell,
  isExpanded,
  onToggle,
  onCast,
  onCastCantrip,
  onConcentrationToggle,
  onEdit,
  onRemove,
  concentratingSpellId,
  castCantripPending,
  onRollDamage,
}: SpellItemProps) {
  const { t } = useTranslation()
  const isConcentrating = concentratingSpellId === spell.id

  return (
    <div
      className={`rounded-xl bg-dnd-surface overflow-hidden
        ${isConcentrating ? 'ring-1 ring-dnd-arcane' : ''}`}
    >
      <button
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left"
        onClick={onToggle}
      >
        <span className="flex-1 font-medium text-sm text-dnd-text">{spell.name}</span>
        <div className="flex gap-1 shrink-0 items-center">
          {spell.is_concentration && (
            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-md bg-dnd-arcane/20 text-dnd-arcane-text border border-dnd-arcane/30">C</span>
          )}
          {spell.is_ritual && (
            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-md bg-dnd-info/20 text-dnd-info-text border border-dnd-info/30">R</span>
          )}
          {spell.is_pinned && <span className="text-xs">&#x1F4CC;</span>}
        </div>
        <span className="text-dnd-text-secondary text-xs ml-1">{isExpanded ? '\u02C4' : '\u02C5'}</span>
      </button>

      {isExpanded && (
        <div className="spell-detail-enter px-3 pb-3 space-y-3 border-t border-dnd-gold-dim/10">
          {/* Description */}
          {spell.description && (
            <p className="text-sm text-dnd-text mt-2 whitespace-pre-wrap leading-relaxed border-l-2 border-dnd-arcane/40 pl-3">
              {spell.description}
            </p>
          )}

          {/* Stats chips */}
          {(spell.casting_time || spell.range_area || spell.components || spell.duration || spell.damage_dice || spell.attack_save) && (
            <div className="grid grid-cols-2 gap-1.5">
              {spell.casting_time && (
                <div className="flex items-center gap-1.5 bg-dnd-chip-bg rounded-lg px-2 py-1.5">
                  <Clock size={12} className="text-dnd-gold-dim shrink-0" />
                  <span className="text-xs font-medium text-dnd-text truncate">{spell.casting_time}</span>
                </div>
              )}
              {spell.range_area && (
                <div className="flex items-center gap-1.5 bg-dnd-chip-bg rounded-lg px-2 py-1.5">
                  <Crosshair size={12} className="text-dnd-gold-dim shrink-0" />
                  <span className="text-xs font-medium text-dnd-text truncate">{spell.range_area}</span>
                </div>
              )}
              {spell.components && (
                <div className="flex items-center gap-1.5 bg-dnd-chip-bg rounded-lg px-2 py-1.5">
                  <FlaskConical size={12} className="text-dnd-gold-dim shrink-0" />
                  <span className="text-xs font-medium text-dnd-text truncate">{spell.components}</span>
                </div>
              )}
              {spell.duration && (
                <div className="flex items-center gap-1.5 bg-dnd-chip-bg rounded-lg px-2 py-1.5">
                  <Timer size={12} className="text-dnd-gold-dim shrink-0" />
                  <span className="text-xs font-medium text-dnd-text truncate">{spell.duration}</span>
                </div>
              )}
              {spell.damage_dice && (
                <div className="flex items-center gap-1.5 bg-dnd-chip-bg rounded-lg px-2 py-1.5">
                  <Swords size={12} className="text-dnd-gold-dim shrink-0" />
                  <span className="text-xs font-medium text-dnd-text truncate">{spell.damage_dice}{spell.damage_type ? ` ${spell.damage_type}` : ''}</span>
                </div>
              )}
              {spell.attack_save && (
                <div className="flex items-center gap-1.5 bg-dnd-chip-bg rounded-lg px-2 py-1.5">
                  <Shield size={12} className="text-dnd-gold-dim shrink-0" />
                  <span className="text-xs font-medium text-dnd-text truncate">{spell.attack_save}</span>
                </div>
              )}
            </div>
          )}

          {/* Higher level note */}
          {spell.higher_level && (
            <div className="bg-dnd-highlight/10 border border-dnd-highlight/20 rounded-lg px-2 py-1.5">
              <span className="text-[10px] uppercase tracking-wide text-dnd-highlight-muted block mb-0.5">{t('character.spells.chip_higher_level')}</span>
              <p className="text-xs text-dnd-highlight-muted leading-relaxed">{spell.higher_level}</p>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex gap-2 flex-wrap border-t border-dnd-gold-dim/10 pt-2">
            {spell.level === 0 ? (
              <button
                onClick={onCastCantrip}
                disabled={castCantripPending}
                className="flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg
                           bg-dnd-success/20 text-dnd-success-text border border-dnd-success/30
                           active:opacity-60 disabled:opacity-30"
              >
                <Sparkles size={12} />
                {t('character.spells.cast_cantrip')}
              </button>
            ) : (
              <button
                onClick={onCast}
                className="flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg
                           bg-dnd-success/20 text-dnd-success-text border border-dnd-success/30
                           active:opacity-60"
              >
                <Sparkles size={12} />
                {t('character.spells.cast')}
              </button>
            )}

            {spell.is_concentration && (
              <button
                onClick={onConcentrationToggle}
                className={`flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg
                            border active:opacity-60
                            ${isConcentrating
                              ? 'bg-[var(--dnd-danger)]/20 text-[var(--dnd-danger)] border-[var(--dnd-danger)]/30'
                              : 'bg-dnd-arcane/20 text-dnd-arcane-text border-dnd-arcane/30'
                            }`}
              >
                <Ban size={12} />
                {isConcentrating
                  ? t('character.spells.stop_concentration')
                  : t('character.spells.concentration')}
              </button>
            )}
            {isExpanded && spell.damage_dice && onRollDamage && (
              <button
                type="button"
                onClick={() => onRollDamage(spell)}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-dnd-surface border border-dnd-gold-dim/30 text-xs hover:border-dnd-gold transition-colors"
              >
                <Dices size={14} className="text-dnd-gold-bright" />
                {t('character.spells.roll_damage.button')}
              </button>
            )}
            <button
              onClick={onEdit}
              className="flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg
                         bg-dnd-info/20 text-dnd-info-text border border-dnd-info/30
                         active:opacity-60"
            >
              <Pencil size={12} />
              {t('character.spells.edit')}
            </button>
            <button
              onClick={onRemove}
              className="flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg
                         bg-[var(--dnd-danger)]/15 text-[var(--dnd-danger)] border border-[var(--dnd-danger)]/30
                         active:opacity-60"
            >
              <Trash2 size={12} />
              {t('character.spells.forget')}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

const SpellItem = React.memo(SpellItemInner)
export default SpellItem

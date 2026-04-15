import React from 'react'
import { useTranslation } from 'react-i18next'
import DndButton from '@/components/DndButton'
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
            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-md bg-dnd-arcane/20 text-[#a569bd] border border-dnd-arcane/30">C</span>
          )}
          {spell.is_ritual && (
            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-md bg-blue-500/20 text-blue-400 border border-blue-500/30">R</span>
          )}
          {spell.is_pinned && <span className="text-xs">&#x1F4CC;</span>}
        </div>
        <span className="text-dnd-text-secondary text-xs ml-1">{isExpanded ? '\u02C4' : '\u02C5'}</span>
      </button>

      {isExpanded && (
        <div className="spell-detail-enter px-3 pb-3 space-y-3 border-t border-dnd-gold-dim/10">
          {/* Description */}
          {spell.description && (
            <p className="text-xs text-dnd-text-secondary mt-2 whitespace-pre-wrap leading-relaxed border-l-2 border-dnd-arcane/40 pl-2">
              {spell.description}
            </p>
          )}

          {/* Stats chips */}
          {(spell.casting_time || spell.range_area || spell.components || spell.duration || spell.damage_dice || spell.attack_save) && (
            <div className="grid grid-cols-2 gap-1.5">
              {spell.casting_time && (
                <div className="flex flex-col bg-black/20 rounded-lg px-2 py-1.5">
                  <span className="text-[10px] uppercase tracking-wide text-dnd-text-secondary mb-0.5">{t('character.spells.chip_casting_time')}</span>
                  <span className="text-xs font-medium text-dnd-text">{spell.casting_time}</span>
                </div>
              )}
              {spell.range_area && (
                <div className="flex flex-col bg-black/20 rounded-lg px-2 py-1.5">
                  <span className="text-[10px] uppercase tracking-wide text-dnd-text-secondary mb-0.5">{t('character.spells.chip_range')}</span>
                  <span className="text-xs font-medium text-dnd-text">{spell.range_area}</span>
                </div>
              )}
              {spell.components && (
                <div className="flex flex-col bg-black/20 rounded-lg px-2 py-1.5">
                  <span className="text-[10px] uppercase tracking-wide text-dnd-text-secondary mb-0.5">{t('character.spells.chip_components')}</span>
                  <span className="text-xs font-medium text-dnd-text">{spell.components}</span>
                </div>
              )}
              {spell.duration && (
                <div className="flex flex-col bg-black/20 rounded-lg px-2 py-1.5">
                  <span className="text-[10px] uppercase tracking-wide text-dnd-text-secondary mb-0.5">{t('character.spells.chip_duration')}</span>
                  <span className="text-xs font-medium text-dnd-text">{spell.duration}</span>
                </div>
              )}
              {spell.damage_dice && (
                <div className="flex flex-col bg-black/20 rounded-lg px-2 py-1.5">
                  <span className="text-[10px] uppercase tracking-wide text-dnd-text-secondary mb-0.5">{t('character.spells.chip_damage')}</span>
                  <span className="text-xs font-medium text-dnd-text">{spell.damage_dice}{spell.damage_type ? ` ${spell.damage_type}` : ''}</span>
                </div>
              )}
              {spell.attack_save && (
                <div className="flex flex-col bg-black/20 rounded-lg px-2 py-1.5">
                  <span className="text-[10px] uppercase tracking-wide text-dnd-text-secondary mb-0.5">{t('character.spells.chip_attack_save')}</span>
                  <span className="text-xs font-medium text-dnd-text">{spell.attack_save}</span>
                </div>
              )}
            </div>
          )}

          {/* Higher level note */}
          {spell.higher_level && (
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg px-2 py-1.5">
              <span className="text-[10px] uppercase tracking-wide text-amber-400/70 block mb-0.5">{t('character.spells.chip_higher_level')}</span>
              <p className="text-xs text-amber-200/80 leading-relaxed">{spell.higher_level}</p>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex gap-2 flex-wrap border-t border-dnd-gold-dim/10 pt-2">
            {spell.level === 0 ? (
              <DndButton
                variant="secondary"
                onClick={onCastCantrip}
                disabled={castCantripPending}
                className="!text-xs !px-3 !py-2 !min-h-0 !bg-dnd-success/20 !text-[#2ecc71] !border-dnd-success/30"
              >
                {t('character.spells.cast_cantrip')}
              </DndButton>
            ) : (
              <DndButton
                variant="secondary"
                onClick={onCast}
                className="!text-xs !px-3 !py-2 !min-h-0 !bg-dnd-success/20 !text-[#2ecc71] !border-dnd-success/30"
              >
                {t('character.spells.cast')}
              </DndButton>
            )}

            {spell.is_concentration && (
              <DndButton
                variant="secondary"
                onClick={onConcentrationToggle}
                className={`!text-xs !px-3 !py-2 !min-h-0 ${
                  isConcentrating
                    ? '!bg-[var(--dnd-danger)]/20 !text-[var(--dnd-danger)] !border-[var(--dnd-danger)]/30'
                    : '!bg-dnd-arcane/20 !text-[#a569bd] !border-dnd-arcane/30'
                }`}
              >
                {isConcentrating
                  ? t('character.spells.stop_concentration')
                  : t('character.spells.concentration')}
              </DndButton>
            )}
            <DndButton
              variant="secondary"
              onClick={onEdit}
              className="!text-xs !px-3 !py-2 !min-h-0 !bg-blue-500/20 !text-blue-400 !border-blue-500/30"
            >
              {t('character.spells.edit')}
            </DndButton>
            <DndButton
              variant="danger"
              onClick={onRemove}
              className="!text-xs !px-3 !py-2 !min-h-0"
            >
              {t('character.spells.forget')}
            </DndButton>
          </div>
        </div>
      )}
    </div>
  )
}

const SpellItem = React.memo(SpellItemInner)
export default SpellItem

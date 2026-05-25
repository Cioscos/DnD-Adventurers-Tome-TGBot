import React, { useState, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Clock, Timer, Pencil, Trash2, Ban, MoreVertical, Info } from 'lucide-react'
import {
  GiCrosshair as Crosshair, GiPotionBall as FlaskConical,
  GiCrossedSwords as Swords, GiCheckedShield as Shield,
  GiSparkles as Sparkles,
} from 'react-icons/gi'
import type { Spell } from '@/types'

interface SpellItemProps {
  spell: Spell
  isExpanded: boolean
  onToggle: () => void
  onUse: () => void
  onConcentrationToggle: () => void
  onEdit: () => void
  onRemove: () => void
  concentratingSpellId: number | null
  usePending: boolean
}

function SpellItemInner({
  spell,
  isExpanded,
  onToggle,
  onUse,
  onConcentrationToggle,
  onEdit,
  onRemove,
  concentratingSpellId,
  usePending,
}: SpellItemProps) {
  const { t } = useTranslation()
  const isConcentrating = concentratingSpellId === spell.id
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuOpen) return
    const close = (e: Event) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('touchstart', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('touchstart', close)
    }
  }, [menuOpen])

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
        <span className="text-dnd-text-muted text-xs ml-1">{isExpanded ? '\u02C4' : '\u02C5'}</span>
      </button>

      {isExpanded && (
        <div className="spell-detail-enter px-3 pb-3 space-y-3 border-t border-dnd-gold-dim/10">
          {/* Description */}
          {spell.description && (
            <p className="text-sm text-dnd-text mt-2 whitespace-pre-wrap leading-relaxed italic">
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

          {/* Concentration workflow hint — clarifies that conc starts on cast,
              and the toggle button is for manual control only. */}
          {spell.is_concentration && (
            <div className="flex items-start gap-1.5 text-[11px] text-dnd-text-muted font-body italic leading-snug">
              <Info size={11} className="text-dnd-arcane-bright shrink-0 mt-0.5" />
              <span>{t('character.spells.concentration_help')}</span>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex gap-2 flex-wrap border-t border-dnd-gold-dim/10 pt-2">
            <button
              onClick={onUse}
              disabled={usePending}
              className="flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg
                         bg-dnd-success/20 text-dnd-success-text border border-dnd-success/30
                         active:opacity-60 disabled:opacity-30"
            >
              <Sparkles size={12} />
              {t('character.spells.use')}
            </button>

            {spell.is_concentration && (
              <button
                onClick={onConcentrationToggle}
                title={t('character.spells.concentration_button_title')}
                aria-label={t('character.spells.concentration_button_title')}
                className={`flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg
                            border active:opacity-60 cursor-help
                            ${isConcentrating
                              ? 'bg-[var(--dnd-danger)]/20 text-[var(--dnd-danger)] border-[var(--dnd-danger)]/30'
                              : 'bg-dnd-arcane/20 text-dnd-arcane-text border-dnd-arcane/30'
                            }`}
              >
                {isConcentrating ? <Ban size={12} /> : <FlaskConical size={12} />}
                {isConcentrating
                  ? t('character.spells.stop_concentration')
                  : t('character.spells.concentration')}
              </button>
            )}
            <div ref={menuRef} className="relative ml-auto flex items-center">
              <button
                onClick={() => setMenuOpen((v) => !v)}
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                className="flex items-center justify-center w-11 h-9 rounded-lg
                           bg-dnd-surface-raised border border-dnd-border
                           text-dnd-text-muted hover:text-dnd-gold-bright active:opacity-60"
                title={t('character.spells.more_actions', { defaultValue: 'Altre azioni' })}
              >
                <MoreVertical size={14} />
              </button>
              {menuOpen && (
                <div
                  role="menu"
                  className="absolute right-0 bottom-full mb-1 z-20 min-w-[160px]
                             rounded-xl border border-dnd-gold-dim/40 bg-dnd-surface-raised
                             shadow-parchment-md overflow-hidden"
                >
                  <button
                    role="menuitem"
                    onClick={() => { setMenuOpen(false); onEdit() }}
                    className="w-full flex items-center gap-2 px-3 py-2.5 text-sm font-body text-dnd-text
                               hover:bg-dnd-info/10 active:opacity-70 text-left"
                  >
                    <Pencil size={14} className="text-dnd-info-text" />
                    {t('character.spells.edit')}
                  </button>
                  <button
                    role="menuitem"
                    onClick={() => { setMenuOpen(false); onRemove() }}
                    className="w-full flex items-center gap-2 px-3 py-2.5 text-sm font-body
                               text-[var(--dnd-danger)] border-t border-dnd-border
                               hover:bg-[var(--dnd-danger)]/10 active:opacity-70 text-left"
                  >
                    <Trash2 size={14} />
                    {t('character.spells.forget')}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const SpellItem = React.memo(SpellItemInner)
export default SpellItem

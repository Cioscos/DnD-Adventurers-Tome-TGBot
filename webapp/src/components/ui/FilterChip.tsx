import React from 'react'
import { m } from 'framer-motion'

interface FilterChipProps {
  label: React.ReactNode
  selected: boolean
  onToggle: () => void
  count?: number
  icon?: React.ReactNode
  tone?: 'gold' | 'arcane' | 'neutral'
  className?: string
  'aria-label'?: string
}

/** Toggleable filter chip with selected/active styling.
 *  44px minimum touch target via min-h. */
export default function FilterChip({
  label,
  selected,
  onToggle,
  count,
  icon,
  tone = 'gold',
  className = '',
  'aria-label': ariaLabel,
}: FilterChipProps) {
  const baseColors = tone === 'arcane'
    ? selected
      ? 'bg-[rgba(155,89,182,0.18)] border-dnd-arcane/70 text-dnd-arcane-bright shadow-halo-arcane'
      : 'bg-dnd-surface border-dnd-border text-dnd-text-muted hover:text-dnd-arcane-bright/80'
    : tone === 'neutral'
      ? selected
        ? 'bg-dnd-surface-raised border-dnd-border-strong text-dnd-text'
        : 'bg-dnd-surface border-dnd-border text-dnd-text-muted'
      : selected
        ? 'bg-dnd-chip-bg border-dnd-gold/70 text-dnd-gold-bright shadow-halo-gold'
        : 'bg-dnd-surface border-dnd-border text-dnd-text-muted hover:text-dnd-gold-bright/80'

  return (
    <m.button
      type="button"
      onClick={onToggle}
      whileTap={{ scale: 0.95 }}
      aria-pressed={selected}
      aria-label={ariaLabel}
      className={`inline-flex items-center gap-1.5 min-h-[44px] px-3 py-1.5 rounded-full border font-cinzel uppercase text-[11px] tracking-widest transition-colors ${baseColors} ${className}`}
    >
      {icon && <span className="shrink-0 -ml-0.5">{icon}</span>}
      <span>{label}</span>
      {typeof count === 'number' && (
        <span className="ml-0.5 px-1.5 rounded-full bg-dnd-surface/60 text-[10px] font-mono">
          {count}
        </span>
      )}
    </m.button>
  )
}

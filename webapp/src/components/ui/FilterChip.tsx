import React from 'react'
import { m } from 'framer-motion'

interface FilterChipProps {
  label: React.ReactNode
  selected: boolean
  onToggle: () => void
  count?: number
  icon?: React.ReactNode
  tone?: 'gold' | 'arcane' | 'neutral' | 'danger' | 'success'
  className?: string
  'aria-label'?: string
}

/** Per-tone selected/idle classes. gold/arcane carry a halo (attention signal);
 *  neutral/danger/success are flat semantic fills. danger/success keep a faint
 *  colored text even when idle so the meaning reads before selection (#47). */
const TONE_STYLES: Record<
  NonNullable<FilterChipProps['tone']>,
  { on: string; off: string }
> = {
  gold: {
    on: 'bg-dnd-chip-bg border-dnd-gold/70 text-dnd-gold-bright shadow-halo-gold',
    off: 'bg-dnd-surface border-dnd-border text-dnd-text-muted hover:text-dnd-gold-bright/80',
  },
  arcane: {
    on: 'bg-[rgba(155,89,182,0.18)] border-dnd-arcane/70 text-dnd-arcane-bright shadow-halo-arcane',
    off: 'bg-dnd-surface border-dnd-border text-dnd-text-muted hover:text-dnd-arcane-bright/80',
  },
  neutral: {
    on: 'bg-dnd-surface-raised border-dnd-border-strong text-dnd-text',
    off: 'bg-dnd-surface border-dnd-border text-dnd-text-muted',
  },
  danger: {
    on: 'bg-dnd-crimson/15 border-dnd-crimson/70 text-dnd-crimson-bright',
    off: 'bg-dnd-surface border-dnd-border text-dnd-crimson/70 hover:text-dnd-crimson-bright',
  },
  success: {
    on: 'bg-dnd-emerald/15 border-dnd-emerald/70 text-dnd-emerald-bright',
    off: 'bg-dnd-surface border-dnd-border text-dnd-emerald/70 hover:text-dnd-emerald-bright',
  },
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
  const baseColors = TONE_STYLES[tone][selected ? 'on' : 'off']

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

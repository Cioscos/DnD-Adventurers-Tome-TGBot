import React from 'react'
import { m } from 'framer-motion'

export interface ChipSelectOption {
  value: string
  label: React.ReactNode
  icon?: React.ReactNode
  disabled?: boolean
}

interface ChipSelectProps {
  label?: string
  options: ChipSelectOption[]
  value: string
  onChange: (value: string) => void
  /** Render as a grid with N columns; omitted → flex-wrap row. */
  columns?: 2 | 3 | 4 | 5
  /** With `columns`, an orphan last chip spans the full row (chip-grid rule). */
  spanOrphan?: boolean
  disabled?: boolean
  className?: string
}

// Tailwind needs literal class names — no template `grid-cols-${n}`.
const GRID_COLS: Record<number, string> = {
  2: 'grid-cols-2',
  3: 'grid-cols-3',
  4: 'grid-cols-4',
  5: 'grid-cols-5',
}

/** Single-select chip group — the guided replacement for native `<select>`
 *  on short enumerable lists. Same visual language as the ItemForm
 *  subtype/die chips. */
export default function ChipSelect({
  label,
  options,
  value,
  onChange,
  columns,
  spanOrphan = true,
  disabled = false,
  className = '',
}: ChipSelectProps) {
  const layout = columns
    ? `grid ${GRID_COLS[columns]} gap-2`
    : 'flex flex-wrap gap-2'

  return (
    <div className={className}>
      {label && (
        <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
          {label}
        </label>
      )}
      <div className={layout} role="radiogroup" aria-label={label}>
        {options.map((opt, idx) => {
          const active = opt.value === value
          const orphanSpan =
            columns && spanOrphan && idx === options.length - 1 && options.length % columns === 1
              ? 'col-span-full'
              : ''
          return (
            <m.button
              key={opt.value}
              type="button"
              role="radio"
              aria-checked={active}
              disabled={disabled || opt.disabled}
              onClick={() => onChange(opt.value)}
              whileTap={disabled || opt.disabled ? undefined : { scale: 0.95 }}
              className={`min-h-[44px] px-3 py-2 rounded-xl text-sm font-medium transition-colors break-words
                inline-flex items-center justify-center gap-1.5 ${orphanSpan}
                disabled:opacity-40 disabled:cursor-not-allowed
                ${active
                  ? 'bg-dnd-gold text-dnd-ink shadow-halo-gold'
                  : 'bg-dnd-surface-raised text-dnd-text border border-dnd-border'}`}
            >
              {opt.icon && <span className="shrink-0">{opt.icon}</span>}
              <span>{opt.label}</span>
            </m.button>
          )
        })}
      </div>
    </div>
  )
}

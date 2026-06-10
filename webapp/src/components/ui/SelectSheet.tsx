import React, { useState } from 'react'
import { ChevronDown, Check } from 'lucide-react'
import Sheet from './Sheet'

export interface SelectSheetOption {
  value: string
  label: string
  description?: string
  icon?: React.ReactNode
}

interface SelectSheetProps {
  label?: string
  /** Sheet title; defaults to `label`. */
  title?: string
  options: SelectSheetOption[]
  value: string
  onChange: (value: string) => void
  /** Trigger text while no value is selected (pass a translated string). */
  placeholder?: string
  disabled?: boolean
  /** z-index of the picker sheet — raise it when the trigger already lives
   *  inside another overlay (default sits above the standard z-50 Sheet). */
  zClassName?: string
  className?: string
}

/** Bottom-sheet option picker — the guided replacement for native `<select>`
 *  on long or dynamic lists. The trigger mimics the old select field. */
export default function SelectSheet({
  label,
  title,
  options,
  value,
  onChange,
  placeholder = '…',
  disabled = false,
  zClassName = 'z-[60]',
  className = '',
}: SelectSheetProps) {
  const [open, setOpen] = useState(false)
  const selected = options.find((o) => o.value === value)

  const pick = (v: string) => {
    setOpen(false)
    onChange(v)
  }

  return (
    <div className={className}>
      {label && (
        <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
          {label}
        </label>
      )}
      <button
        type="button"
        onClick={() => setOpen(true)}
        disabled={disabled}
        aria-haspopup="dialog"
        className="w-full px-3 py-2.5 min-h-[48px] rounded-lg bg-dnd-surface border-b-2 border-dnd-border
                   outline-none font-body text-sm text-left transition-colors
                   flex items-center justify-between gap-2
                   disabled:opacity-40 disabled:cursor-not-allowed"
      >
        <span className={`flex items-center gap-2 min-w-0 ${selected ? 'text-dnd-text' : 'text-dnd-text-faint'}`}>
          {selected?.icon && <span className="shrink-0">{selected.icon}</span>}
          <span className="truncate">{selected ? selected.label : placeholder}</span>
        </span>
        <ChevronDown size={16} className="text-dnd-gold-dim shrink-0" />
      </button>

      <Sheet open={open} onClose={() => setOpen(false)} title={title ?? label} zClassName={zClassName}>
        <div className="py-2" role="radiogroup" aria-label={title ?? label}>
          {options.map((opt) => {
            const active = opt.value === value
            return (
              <button
                key={opt.value}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => pick(opt.value)}
                className={`w-full min-h-[48px] px-5 py-2 flex items-center justify-between gap-3 text-left
                  font-body text-sm transition-colors active:bg-dnd-surface-raised
                  ${active ? 'text-dnd-gold-bright' : 'text-dnd-text'}`}
              >
                <span className="flex items-center gap-2.5 min-w-0">
                  {opt.icon && <span className="shrink-0">{opt.icon}</span>}
                  <span className="min-w-0">
                    <span className="block break-words">{opt.label}</span>
                    {opt.description && (
                      <span className="block text-xs text-dnd-text-muted italic">{opt.description}</span>
                    )}
                  </span>
                </span>
                {active && <Check size={18} className="text-dnd-gold shrink-0" />}
              </button>
            )
          })}
        </div>
      </Sheet>
    </div>
  )
}

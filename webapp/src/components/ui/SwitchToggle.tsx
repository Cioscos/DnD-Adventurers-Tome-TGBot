import { m } from 'framer-motion'
import { spring } from '@/styles/motion'
import { haptic } from '@/auth/telegram'

interface SwitchToggleProps {
  checked: boolean
  onChange: (next: boolean) => void
  label?: React.ReactNode
  hint?: React.ReactNode
  icon?: React.ReactNode
  disabled?: boolean
  'aria-label'?: string
}

/** Pill-style boolean switch matching the design at Settings dice-3d.
 *  Wraps label + hint in a click-target ≥44px when label/hint provided. */
export default function SwitchToggle({
  checked,
  onChange,
  label,
  hint,
  icon,
  disabled = false,
  'aria-label': ariaLabel,
}: SwitchToggleProps) {
  const toggle = () => {
    if (disabled) return
    haptic.light()
    onChange(!checked)
  }

  const knob = (
    <m.button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      onClick={(e) => {
        e.stopPropagation()
        toggle()
      }}
      disabled={disabled}
      className={`w-12 h-7 rounded-full transition-colors shrink-0 border flex items-center px-0.5 disabled:opacity-50
        ${checked
          ? 'bg-gradient-to-r from-dnd-gold-dim to-dnd-gold-bright border-dnd-gold-bright shadow-[0_0_8px_var(--dnd-gold-glow)] justify-end'
          : 'bg-dnd-surface border-dnd-border justify-start'}`}
      whileTap={disabled ? undefined : { scale: 0.92 }}
    >
      <m.span
        layout
        transition={spring.snappy}
        className="block w-5 h-5 rounded-full bg-dnd-parchment shadow-parchment-md"
      />
    </m.button>
  )

  if (!label && !hint && !icon) return knob

  return (
    <label
      onClick={(e) => {
        if (e.target instanceof HTMLElement && e.target.closest('button[role="switch"]')) return
        toggle()
      }}
      className={`flex items-center justify-between gap-3 min-h-[44px] cursor-pointer ${disabled ? 'opacity-60 pointer-events-none' : ''}`}
    >
      <div className="flex items-start gap-2 flex-1 min-w-0">
        {icon && <span className="text-dnd-gold-bright shrink-0 mt-0.5">{icon}</span>}
        <div className="min-w-0">
          {label && (
            <p className="font-display font-bold text-dnd-gold-bright">{label}</p>
          )}
          {hint && (
            <p className="text-xs text-dnd-text-muted mt-0.5 font-body italic">{hint}</p>
          )}
        </div>
      </div>
      {knob}
    </label>
  )
}

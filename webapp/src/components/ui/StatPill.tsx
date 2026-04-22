import React, { useState, useRef, useEffect } from 'react'
import { m } from 'framer-motion'

interface StatPillProps {
  icon?: React.ReactNode
  label?: string
  value: React.ReactNode
  tone?: 'default' | 'gold' | 'arcane' | 'crimson' | 'emerald' | 'cobalt' | 'amber'
  size?: 'sm' | 'md'
  onClick?: () => void
  /**
   * Hide `label` and `value`, show only `icon`.
   * When true, the component becomes focusable (button) with an aria-label.
   */
  iconOnly?: boolean
  /**
   * When `iconOnly` is true, tapping reveals the value inline for `revealDurationMs`
   * then returns to icon-only. Tapping again while revealed resets the timer.
   */
  revealOnTap?: boolean
  revealDurationMs?: number
  'aria-label'?: string
  className?: string
}

function toneClasses(tone: StatPillProps['tone']): string {
  switch (tone) {
    case 'gold':
      return 'bg-dnd-chip-bg border-dnd-gold/40 text-dnd-gold-bright'
    case 'arcane':
      return 'bg-[rgba(155,89,182,0.12)] border-dnd-arcane/40 text-dnd-arcane-bright'
    case 'crimson':
      return 'bg-[rgba(179,58,58,0.12)] border-dnd-crimson/40 text-[var(--dnd-crimson-bright)]'
    case 'emerald':
      return 'bg-[rgba(63,166,106,0.12)] border-dnd-emerald/40 text-[var(--dnd-emerald-bright)]'
    case 'cobalt':
      return 'bg-[rgba(58,124,165,0.12)] border-dnd-cobalt/40 text-[var(--dnd-cobalt-bright)]'
    case 'amber':
      return 'bg-[rgba(232,165,71,0.12)] border-dnd-amber/50 text-[var(--dnd-amber)]'
    case 'default':
    default:
      return 'bg-dnd-surface border-dnd-border text-dnd-text'
  }
}

function StatPillInner({
  icon,
  label,
  value,
  tone = 'default',
  size = 'md',
  onClick,
  iconOnly = false,
  revealOnTap = false,
  revealDurationMs = 2000,
  'aria-label': ariaLabelProp,
  className = '',
}: StatPillProps) {
  const [revealed, setRevealed] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  const handleClick = () => {
    if (iconOnly && revealOnTap) {
      setRevealed(true)
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => setRevealed(false), revealDurationMs)
    }
    onClick?.()
  }

  const isInteractive = !!onClick || (iconOnly && revealOnTap)
  const showValue = !iconOnly || revealed
  const showLabel = !iconOnly && !!label
  const padding = size === 'sm' ? 'px-2 py-1 text-[11px]' : 'px-2.5 py-1 text-xs'
  const cls = `inline-flex items-center gap-1.5 rounded-full border font-medium font-body ${padding} ${toneClasses(tone)} ${isInteractive ? 'cursor-pointer' : ''} ${className}`
  const Component: React.ElementType = isInteractive ? m.button : m.span

  const resolvedAriaLabel =
    ariaLabelProp ??
    (iconOnly && typeof value === 'string' ? value : undefined)

  return (
    <Component
      className={cls}
      onClick={isInteractive ? handleClick : undefined}
      whileTap={isInteractive ? { scale: 0.95 } : undefined}
      aria-label={resolvedAriaLabel}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      {showLabel && <span className="opacity-70">{label}</span>}
      {showValue && <span className="font-mono font-bold">{value}</span>}
    </Component>
  )
}

const StatPill = React.memo(StatPillInner)
export default StatPill

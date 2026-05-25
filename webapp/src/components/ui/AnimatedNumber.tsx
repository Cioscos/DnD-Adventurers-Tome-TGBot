import { useEffect } from 'react'
import { m, useSpring, useTransform, useReducedMotion } from 'framer-motion'

interface AnimatedNumberProps {
  value: number
  /** Decimal places to render. Defaults to 0 (integer). */
  precision?: number
  /** Spring stiffness. Defaults to 140 (gentle scrub for HP/AC/level). */
  stiffness?: number
  /** Spring damping. Defaults to 24. */
  damping?: number
  className?: string
  /** Prefix string (e.g. "+"). Not animated. */
  prefix?: string
  /** Suffix string (e.g. " XP"). Not animated. */
  suffix?: string
  /** Locale for thousand separators. Defaults to Italian grouping ('.'). */
  locale?: string
}

/**
 * Mono, tabular-nums digit scrubber.
 * Used for HP/AC/XP/level/currency/stepper deltas where the user benefits
 * from seeing the value transition rather than snap. Honors
 * prefers-reduced-motion by snapping instantly.
 */
export default function AnimatedNumber({
  value,
  precision = 0,
  stiffness = 140,
  damping = 24,
  className = '',
  prefix = '',
  suffix = '',
  locale = 'it-IT',
}: AnimatedNumberProps) {
  const reduced = useReducedMotion()
  const spring = useSpring(value, { stiffness, damping, mass: 0.6 })

  useEffect(() => {
    if (reduced) {
      spring.jump(value)
    } else {
      spring.set(value)
    }
  }, [value, reduced, spring])

  const display = useTransform(spring, (current) => {
    const factor = Math.pow(10, precision)
    const rounded = Math.round(current * factor) / factor
    const formatted = rounded.toLocaleString(locale, {
      minimumFractionDigits: precision,
      maximumFractionDigits: precision,
    })
    return `${prefix}${formatted}${suffix}`
  })

  return (
    <m.span className={`font-mono tabular-nums ${className}`}>{display}</m.span>
  )
}

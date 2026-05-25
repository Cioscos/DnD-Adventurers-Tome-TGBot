import React from 'react'
import { m } from 'framer-motion'
import { spring } from '@/styles/motion'

interface ProgressTriadProps {
  /** Current value. */
  value: number
  /** Max value (capacity). */
  max: number
  /** Optional inline label rendered to the left. */
  label?: React.ReactNode
  /** Optional explicit display string ("12.4 / 150 lb"). Falls back to "{value} / {max}". */
  display?: React.ReactNode
  /** Thresholds (0-1) for emerald → amber → crimson transitions. */
  amberAt?: number
  crimsonAt?: number
  className?: string
  /** Show numeric tag above the bar (default true when label provided). */
  showNumeric?: boolean
}

/** Horizontal mini-progress bar with Semantic Triad coloring.
 *  emerald < amberAt, amber < crimsonAt, crimson when overloaded. */
export default function ProgressTriad({
  value,
  max,
  label,
  display,
  amberAt = 0.7,
  crimsonAt = 1.0,
  className = '',
  showNumeric,
}: ProgressTriadProps) {
  const safeMax = max > 0 ? max : 1
  const pct = value / safeMax
  const pctClamped = Math.max(0, Math.min(1.2, pct))
  const widthPct = Math.min(100, pctClamped * 100)

  const isCrimson = pct >= crimsonAt
  const isAmber = !isCrimson && pct >= amberAt

  const colorCss = isCrimson
    ? 'var(--dnd-crimson-bright)'
    : isAmber
      ? 'var(--dnd-amber)'
      : 'var(--dnd-emerald-bright)'

  const glowRgba = isCrimson
    ? 'rgba(232, 80, 80, 0.5)'
    : isAmber
      ? 'rgba(232, 165, 71, 0.42)'
      : 'rgba(111, 209, 149, 0.38)'

  const showNum = showNumeric ?? !!label

  return (
    <div className={className}>
      {(label || showNum) && (
        <div className="flex items-center justify-between mb-1">
          {label && (
            <span className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim">
              {label}
            </span>
          )}
          {showNum && (
            <span className="text-[11px] font-mono tabular-nums text-dnd-text">
              {display ?? `${value} / ${max}`}
            </span>
          )}
        </div>
      )}
      <div className="h-1.5 w-full rounded-full bg-dnd-surface overflow-hidden border border-dnd-border/60">
        <m.div
          className="h-full origin-left rounded-full"
          style={{
            background: colorCss,
            boxShadow: `0 0 6px ${glowRgba}`,
            width: '100%',
          }}
          initial={false}
          animate={{ scaleX: widthPct / 100 }}
          transition={spring.drift}
        />
      </div>
    </div>
  )
}

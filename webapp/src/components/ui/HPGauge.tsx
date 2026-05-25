import React, { useRef } from 'react'
import { m, useReducedMotion } from 'framer-motion'
import { ease } from '@/styles/motion'

interface HPGaugeProps {
  current: number
  max: number
  temp?: number
  size?: 'sm' | 'md' | 'lg'
  segmented?: boolean
  className?: string
}

const SEGMENTS = 10
const STAGGER_MS = 28

function HPGaugeInner({ current, max, temp = 0, size = 'md', segmented = true, className = '' }: HPGaugeProps) {
  const pct = max > 0 ? Math.min(100, (current / max) * 100) : 0
  const tempPct = max > 0 ? Math.min(100, (temp / max) * 100) : 0
  const reduced = useReducedMotion()

  const prevPctRef = useRef(pct)
  const prevTempPctRef = useRef(tempPct)
  const direction = pct < prevPctRef.current ? 'down' : pct > prevPctRef.current ? 'up' : 'none'
  prevPctRef.current = pct
  prevTempPctRef.current = tempPct

  const height = size === 'sm' ? 'h-1.5' : size === 'lg' ? 'h-3.5' : 'h-2.5'

  let colorVarA: string
  let colorVarB: string
  let glowRgba: string
  let pulse = false

  if (pct > 50) {
    colorVarA = 'var(--dnd-emerald-deep)'
    colorVarB = 'var(--dnd-emerald-bright)'
    glowRgba = 'rgba(63, 166, 106, 0.42)'
  } else if (pct > 25) {
    colorVarA = 'var(--dnd-gold-dim)'
    colorVarB = 'var(--dnd-gold-bright)'
    glowRgba = 'rgba(212, 168, 71, 0.42)'
  } else {
    colorVarA = 'var(--dnd-crimson-deep)'
    colorVarB = 'var(--dnd-crimson-bright)'
    glowRgba = 'rgba(192, 57, 43, 0.5)'
    pulse = true
  }

  if (!segmented) {
    return (
      <div
        className={`relative w-full ${height} rounded-full overflow-hidden bg-dnd-ink/60 border border-dnd-border/60 ${className}`}
      >
        <m.div
          className={`absolute left-0 top-0 h-full w-full rounded-full origin-left ${pulse ? 'animate-pulse-danger' : ''}`}
          style={{
            background: `linear-gradient(90deg, ${colorVarA}, ${colorVarB})`,
            boxShadow: `0 0 8px ${glowRgba}`,
          }}
          initial={false}
          animate={{ scaleX: pct / 100 }}
          transition={{ duration: 0.34, ease: ease.inkSpread }}
        />
        {temp > 0 && (
          <m.div
            className="absolute left-0 top-0 h-full w-full rounded-full opacity-70 origin-left"
            style={{
              background: `repeating-linear-gradient(45deg, var(--dnd-cobalt) 0 4px, var(--dnd-cobalt-bright) 4px 8px)`,
            }}
            initial={false}
            animate={{ scaleX: tempPct / 100 }}
            transition={{ duration: 0.34, ease: ease.inkSpread }}
          />
        )}
      </div>
    )
  }

  const segmentFills = Array.from({ length: SEGMENTS }, (_, i) => {
    const segmentStartPct = i * (100 / SEGMENTS)
    const segmentEndPct = (i + 1) * (100 / SEGMENTS)
    if (pct >= segmentEndPct) return 1
    if (pct <= segmentStartPct) return 0
    return (pct - segmentStartPct) / (100 / SEGMENTS)
  })

  const tempSegmentFills = Array.from({ length: SEGMENTS }, (_, i) => {
    const segmentStartPct = i * (100 / SEGMENTS)
    const segmentEndPct = (i + 1) * (100 / SEGMENTS)
    if (tempPct >= segmentEndPct) return 1
    if (tempPct <= segmentStartPct) return 0
    return (tempPct - segmentStartPct) / (100 / SEGMENTS)
  })

  return (
    <div
      className={`relative w-full ${height} rounded-full overflow-hidden bg-dnd-ink/60 border border-dnd-border/60 flex gap-px ${pulse ? 'animate-pulse-danger' : ''} ${className}`}
    >
      {segmentFills.map((fill, i) => {
        const segmentDelay = reduced
          ? 0
          : direction === 'down'
            ? (SEGMENTS - 1 - i) * (STAGGER_MS / 1000)
            : direction === 'up'
              ? i * (STAGGER_MS / 1000)
              : 0
        return (
          <div key={i} className="relative flex-1 h-full overflow-hidden" style={{ minWidth: 0 }}>
            <m.div
              className="absolute inset-0 origin-left"
              style={{
                background: `linear-gradient(90deg, ${colorVarA}, ${colorVarB})`,
                boxShadow: fill > 0 ? `0 0 6px ${glowRgba}` : 'none',
              }}
              initial={false}
              animate={{ scaleX: fill, opacity: fill > 0 ? 1 : 0 }}
              transition={{
                duration: 0.22,
                ease: ease.inkSpread,
                delay: segmentDelay,
              }}
            />
            {tempSegmentFills[i] > 0 && (
              <m.div
                className="absolute inset-0 origin-left opacity-70"
                style={{
                  background: `repeating-linear-gradient(45deg, var(--dnd-cobalt) 0 4px, var(--dnd-cobalt-bright) 4px 8px)`,
                }}
                initial={false}
                animate={{ scaleX: tempSegmentFills[i] }}
                transition={{ duration: 0.22, ease: ease.inkSpread, delay: segmentDelay }}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

const HPGauge = React.memo(HPGaugeInner)
export default HPGauge

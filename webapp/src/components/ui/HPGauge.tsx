import React from 'react'
import { m } from 'framer-motion'
import { spring } from '@/styles/motion'

interface HPGaugeProps {
  current: number
  max: number
  temp?: number
  size?: 'sm' | 'md' | 'lg'
  segmented?: boolean
  className?: string
}

function HPGaugeInner({ current, max, temp = 0, size = 'md', segmented = true, className = '' }: HPGaugeProps) {
  const pct = max > 0 ? Math.min(100, (current / max) * 100) : 0
  const tempPct = max > 0 ? Math.min(100, (temp / max) * 100) : 0

  const height = size === 'sm' ? 'h-1.5' : size === 'lg' ? 'h-3.5' : 'h-2.5'

  let gradient: string
  let glow: string
  let pulse = false

  if (pct > 50) {
    gradient = 'linear-gradient(90deg, var(--dnd-emerald-deep), var(--dnd-emerald-bright))'
    glow = '0 0 8px rgba(63, 166, 106, 0.4)'
  } else if (pct > 25) {
    gradient = 'linear-gradient(90deg, var(--dnd-gold-dim), var(--dnd-gold-bright))'
    glow = '0 0 8px rgba(212, 168, 71, 0.4)'
  } else {
    gradient = 'linear-gradient(90deg, var(--dnd-crimson-deep), var(--dnd-crimson-bright))'
    glow = '0 0 8px rgba(192, 57, 43, 0.5)'
    pulse = true
  }

  return (
    <div
      className={`relative w-full ${height} rounded-full overflow-hidden bg-dnd-ink/60 border border-dnd-border/60 ${className}`}
    >
      {/* Fill */}
      <m.div
        className={`absolute left-0 top-0 h-full rounded-full ${pulse ? 'animate-pulse-danger' : ''}`}
        style={{ background: gradient, boxShadow: glow }}
        initial={false}
        animate={{ width: `${pct}%` }}
        transition={spring.drift}
      />

      {/* Temp HP diagonal stripe overlay */}
      {temp > 0 && (
        <m.div
          className="absolute left-0 top-0 h-full rounded-full opacity-70"
          style={{
            background: `repeating-linear-gradient(45deg, var(--dnd-cobalt) 0 4px, var(--dnd-cobalt-bright) 4px 8px)`,
          }}
          initial={false}
          animate={{ width: `${tempPct}%` }}
          transition={spring.drift}
        />
      )}

      {/* Segmented tick marks */}
      {segmented && (
        <div className="absolute inset-0 flex pointer-events-none">
          {Array.from({ length: 9 }).map((_, i) => (
            <div
              key={i}
              className="flex-1 border-r border-dnd-ink/30 last:border-r-0"
              style={{ minWidth: 0 }}
            />
          ))}
        </div>
      )}
    </div>
  )
}

const HPGauge = React.memo(HPGaugeInner)
export default HPGauge

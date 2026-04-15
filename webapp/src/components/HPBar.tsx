import React from 'react'

interface HPBarProps {
  current: number
  max: number
  temp?: number
  size?: 'sm' | 'md'
}

function HPBarInner({ current, max, temp = 0, size = 'md' }: HPBarProps) {
  const pct = max > 0 ? Math.min(100, (current / max) * 100) : 0
  const height = size === 'sm' ? 'h-1.5' : 'h-2.5'

  let gradient: string
  let glow: string
  let pulse = false

  if (pct > 50) {
    gradient = 'linear-gradient(90deg, #27ae60, #2ecc71)'
    glow = '0 0 8px rgba(39, 174, 96, 0.4)'
  } else if (pct > 25) {
    gradient = 'linear-gradient(90deg, #d4a847, #f0c040)'
    glow = '0 0 8px rgba(212, 168, 71, 0.4)'
  } else {
    gradient = 'linear-gradient(90deg, #c0392b, #e74c3c)'
    glow = '0 0 8px rgba(192, 57, 43, 0.5)'
    pulse = true
  }

  return (
    <div className={`w-full ${height} rounded-full bg-white/10 overflow-hidden relative`}>
      <div
        className={`h-full rounded-full transition-all duration-500 ${pulse ? 'animate-pulse-danger' : ''}`}
        style={{ width: `${pct}%`, background: gradient, boxShadow: glow }}
      />
      {temp > 0 && (
        <div
          className="absolute top-0 left-0 h-full rounded-full opacity-60"
          style={{
            width: `${Math.min(100, (temp / max) * 100)}%`,
            backgroundColor: 'var(--dnd-info)',
          }}
        />
      )}
    </div>
  )
}

const HPBar = React.memo(HPBarInner)
export default HPBar

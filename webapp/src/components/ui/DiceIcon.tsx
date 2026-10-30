import React from 'react'

type DieSide = 4 | 6 | 8 | 10 | 12 | 20 | 100

interface DiceIconProps {
  sides: DieSide
  size?: number
  className?: string
}

const VIEWBOX = 60
const MIN_TEXT_PX = 12
// Oltre questa dimensione (in unità del viewBox) il numero occupa la faccia interna del d20.
const MAX_FONT_WITH_INNER_FACE = 18

/** Dimensione del numero in unità del viewBox: mai sotto i 12 px alla taglia resa. */
function numeralFontSize(baseFontSize: number, size: number): number {
  return Math.max(baseFontSize, (MIN_TEXT_PX * VIEWBOX) / size)
}

function Numeral({ size, y, baseFontSize, children }: { size: number; y: number; baseFontSize: number; children: React.ReactNode }) {
  const fontSize = numeralFontSize(baseFontSize, size)
  // Il numero ingrandito resta centrato sulla faccia: la linea di base scende di conseguenza.
  const baseline = y + (fontSize - baseFontSize) * 0.35
  return (
    <text x="30" y={baseline} textAnchor="middle" fontSize={fontSize} fill="currentColor" fontFamily="Cinzel, serif" fontWeight="900">
      {children}
    </text>
  )
}

/**
 * Stylized dice icons as inline SVG. Each die shape is distinct
 * (tetrahedron silhouette for d4, cube for d6, octahedron for d8, etc.).
 * currentColor drives the stroke — wrap in `text-dnd-gold` etc.
 */
function DiceIconInner({ sides, size = 48, className = '' }: DiceIconProps) {
  const common = { width: size, height: size, viewBox: '0 0 60 60', fill: 'none', className, 'aria-hidden': true as const }

  switch (sides) {
    case 4:
      return (
        <svg {...common}>
          <polygon points="30,6 52,48 8,48" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" fill="var(--dnd-surface-raised)" />
          <Numeral size={size} y={42} baseFontSize={18}>4</Numeral>
        </svg>
      )
    case 6:
      return (
        <svg {...common}>
          <rect x="10" y="10" width="40" height="40" rx="6" stroke="currentColor" strokeWidth="2" fill="var(--dnd-surface-raised)" />
          <Numeral size={size} y={38} baseFontSize={18}>6</Numeral>
        </svg>
      )
    case 8:
      return (
        <svg {...common}>
          <polygon points="30,6 54,30 30,54 6,30" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" fill="var(--dnd-surface-raised)" />
          <Numeral size={size} y={36} baseFontSize={16}>8</Numeral>
        </svg>
      )
    case 10:
      return (
        <svg {...common}>
          <polygon points="30,4 52,22 46,50 14,50 8,22" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" fill="var(--dnd-surface-raised)" />
          <Numeral size={size} y={36} baseFontSize={14}>10</Numeral>
        </svg>
      )
    case 12:
      return (
        <svg {...common}>
          <polygon points="30,4 52,18 54,44 36,56 24,56 6,44 8,18" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" fill="var(--dnd-surface-raised)" />
          <Numeral size={size} y={36} baseFontSize={14}>12</Numeral>
        </svg>
      )
    case 20:
      return (
        <svg {...common}>
          <polygon points="30,4 54,18 54,42 30,56 6,42 6,18" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" fill="var(--dnd-surface-raised)" />
          {numeralFontSize(14, size) <= MAX_FONT_WITH_INNER_FACE && (
            <polygon points="30,14 44,22 44,38 30,46 16,38 16,22" stroke="currentColor" strokeWidth="1" fill="none" opacity="0.5" />
          )}
          <Numeral size={size} y={36} baseFontSize={14}>20</Numeral>
        </svg>
      )
    case 100:
      return (
        <svg {...common}>
          <polygon points="30,6 54,22 48,50 12,50 6,22" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" fill="var(--dnd-surface-raised)" />
          <Numeral size={size} y={36} baseFontSize={13}>%</Numeral>
        </svg>
      )
  }
}

const DiceIcon = React.memo(DiceIconInner)
export default DiceIcon

import React from 'react'

type DieSide = 4 | 6 | 8 | 10 | 12 | 20 | 100

interface DiceIconProps {
  sides: DieSide
  size?: number
  className?: string
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
          <text x="30" y="42" textAnchor="middle" fontSize="18" fill="currentColor" fontFamily="Cinzel, serif" fontWeight="900">4</text>
        </svg>
      )
    case 6:
      return (
        <svg {...common}>
          <rect x="10" y="10" width="40" height="40" rx="6" stroke="currentColor" strokeWidth="2" fill="var(--dnd-surface-raised)" />
          <text x="30" y="38" textAnchor="middle" fontSize="18" fill="currentColor" fontFamily="Cinzel, serif" fontWeight="900">6</text>
        </svg>
      )
    case 8:
      return (
        <svg {...common}>
          <polygon points="30,6 54,30 30,54 6,30" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" fill="var(--dnd-surface-raised)" />
          <text x="30" y="36" textAnchor="middle" fontSize="16" fill="currentColor" fontFamily="Cinzel, serif" fontWeight="900">8</text>
        </svg>
      )
    case 10:
      return (
        <svg {...common}>
          <polygon points="30,4 52,22 46,50 14,50 8,22" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" fill="var(--dnd-surface-raised)" />
          <text x="30" y="36" textAnchor="middle" fontSize="14" fill="currentColor" fontFamily="Cinzel, serif" fontWeight="900">10</text>
        </svg>
      )
    case 12:
      return (
        <svg {...common}>
          <polygon points="30,4 52,18 54,44 36,56 24,56 6,44 8,18" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" fill="var(--dnd-surface-raised)" />
          <text x="30" y="36" textAnchor="middle" fontSize="14" fill="currentColor" fontFamily="Cinzel, serif" fontWeight="900">12</text>
        </svg>
      )
    case 20:
      return (
        <svg {...common}>
          <polygon points="30,4 54,18 54,42 30,56 6,42 6,18" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" fill="var(--dnd-surface-raised)" />
          <polygon points="30,14 44,22 44,38 30,46 16,38 16,22" stroke="currentColor" strokeWidth="1" fill="none" opacity="0.5" />
          <text x="30" y="36" textAnchor="middle" fontSize="14" fill="currentColor" fontFamily="Cinzel, serif" fontWeight="900">20</text>
        </svg>
      )
    case 100:
      return (
        <svg {...common}>
          <polygon points="30,6 54,22 48,50 12,50 6,22" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" fill="var(--dnd-surface-raised)" />
          <text x="30" y="36" textAnchor="middle" fontSize="13" fill="currentColor" fontFamily="Cinzel, serif" fontWeight="900">%</text>
        </svg>
      )
  }
}

const DiceIcon = React.memo(DiceIconInner)
export default DiceIcon

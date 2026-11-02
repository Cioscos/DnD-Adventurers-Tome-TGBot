import React from 'react'
import { m } from 'framer-motion'
import { spring } from '@/styles/motion'

export type SurfaceVariant = 'flat' | 'elevated' | 'arcane' | 'ember' | 'sigil' | 'tome' | 'parchment'

interface SurfaceProps {
  children: React.ReactNode
  className?: string
  variant?: SurfaceVariant
  ornamented?: boolean
  interactive?: boolean
  asMotion?: boolean
  layoutId?: string
  onClick?: (e: React.MouseEvent<HTMLDivElement>) => void
  style?: React.CSSProperties
  tabIndex?: number
  role?: string
  'aria-label'?: string
}

function variantStyles(variant: SurfaceVariant): string {
  switch (variant) {
    case 'elevated':
      return 'bg-dnd-surface-raised border border-dnd-gold-dim/50 shadow-parchment-lg'
    case 'tome':
      return 'bg-gradient-parchment border border-dnd-border-strong shadow-parchment-xl surface-parchment'
    case 'parchment':
      return 'bg-gradient-parchment border border-dnd-border shadow-parchment-md surface-parchment'
    case 'arcane':
      return 'bg-gradient-arcane-mist border border-dnd-arcane/40 shadow-halo-arcane'
    case 'ember':
      return 'bg-dnd-surface border border-dnd-crimson/50 shadow-halo-danger'
    case 'sigil':
      return 'bg-gradient-parchment border border-dnd-gold/40 shadow-parchment-xl surface-parchment'
    case 'flat':
    default:
      return 'bg-dnd-surface border border-transparent'
  }
}

function SurfaceInner({
  children,
  className = '',
  variant = 'flat',
  ornamented = false,
  interactive = false,
  asMotion = false,
  layoutId,
  onClick,
  style,
  tabIndex,
  role,
  'aria-label': ariaLabel,
}: SurfaceProps) {
  const base = 'relative rounded-2xl p-4 transition-shadow duration-300'
  const interactiveClass = interactive || onClick
    ? 'cursor-pointer active:scale-[0.98] will-change-transform'
    : ''
  const cls = `${base} ${variantStyles(variant)} ${interactiveClass} ${className}`

  // Senza ornamento i figli sono diretti: space-y/divide-y passati in className arrivano a loro
  // (un wrapper `display: contents` li assorbiva tutti: spaziature a 0).
  // Con ornamento c'è un wrapper vero: le classi di spaziatura dei figli vanno su di lui.
  const childSpacing = className.split(/\s+/).filter((c) => /^(space-[xy]-|divide-)/.test(c)).join(' ')
  const content = ornamented
    ? <div className={`relative z-[1] pt-3 px-2 pb-2 ${childSpacing}`}>{children}</div>
    : children

  if (asMotion || layoutId) {
    return (
      <m.div
        layoutId={layoutId}
        className={cls}
        onClick={onClick}
        style={style}
        tabIndex={tabIndex}
        role={role}
        aria-label={ariaLabel}
        whileTap={interactive || onClick ? { scale: 0.98 } : undefined}
        transition={spring.press}
      >
        {content}
      </m.div>
    )
  }

  return (
    <div
      className={cls}
      onClick={onClick}
      style={style}
      tabIndex={tabIndex}
      role={role}
      aria-label={ariaLabel}
    >
      {content}
    </div>
  )
}

const Surface = React.memo(SurfaceInner)
export default Surface

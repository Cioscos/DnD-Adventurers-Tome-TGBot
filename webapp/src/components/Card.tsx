import React from 'react'

interface CardProps {
  children: React.ReactNode
  className?: string
  variant?: 'default' | 'elevated'
  onClick?: (e: React.MouseEvent<HTMLDivElement>) => void
}

function CardInner({ children, className = '', variant = 'default', onClick }: CardProps) {
  const base = 'rounded-2xl p-4 transition-all duration-150 active:opacity-70'
  const cursor = onClick ? 'cursor-pointer' : ''

  const variantStyles =
    variant === 'elevated'
      ? 'bg-dnd-surface-elevated border border-dnd-gold-dim shadow-dnd-glow'
      : 'bg-dnd-surface'

  return (
    <div className={`${base} ${variantStyles} ${cursor} ${className}`} onClick={onClick}>
      {children}
    </div>
  )
}

const Card = React.memo(CardInner)
export default Card

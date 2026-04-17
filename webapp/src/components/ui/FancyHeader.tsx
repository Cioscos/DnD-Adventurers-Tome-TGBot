import React from 'react'
import { FlourishDivider } from './Ornament'

interface FancyHeaderProps {
  title: string
  subtitle?: string
  align?: 'left' | 'center'
  className?: string
  size?: 'md' | 'lg' | 'xl'
}

function FancyHeaderInner({
  title,
  subtitle,
  align = 'center',
  className = '',
  size = 'lg',
}: FancyHeaderProps) {
  const titleSize = size === 'xl' ? 'text-4xl md:text-5xl' : size === 'md' ? 'text-2xl' : 'text-3xl md:text-4xl'
  const alignCls = align === 'center' ? 'items-center text-center' : 'items-start text-left'

  return (
    <div className={`flex flex-col gap-2 ${alignCls} ${className}`}>
      <div className="flex items-center gap-3 w-full">
        {align === 'center' && (
          <div className="flex-1 text-dnd-gold-dim">
            <FlourishDivider />
          </div>
        )}
        <h1
          className={`font-display font-bold ${titleSize} text-dnd-gold-bright leading-tight shrink-0`}
          style={{
            textShadow: '0 2px 8px var(--dnd-gold-glow), 0 0 1px rgba(0,0,0,0.5)',
          }}
        >
          {title}
        </h1>
        {align === 'center' && (
          <div className="flex-1 text-dnd-gold-dim">
            <FlourishDivider />
          </div>
        )}
      </div>
      {subtitle && (
        <p className="text-sm text-dnd-text-muted font-body italic">{subtitle}</p>
      )}
    </div>
  )
}

const FancyHeader = React.memo(FancyHeaderInner)
export default FancyHeader

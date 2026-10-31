import React from 'react'
import { FlourishDivider } from './Ornament'

interface SectionDividerProps {
  children: React.ReactNode
  icon?: React.ReactNode
  align?: 'left' | 'center'
  className?: string
}

function SectionDividerInner({ children, icon, align = 'left', className = '' }: SectionDividerProps) {
  if (align === 'center') {
    return (
      <div className={`flex items-center gap-2 mt-5 mb-3 text-dnd-gold-dim ${className}`}>
        {/* Le flourish restano visibili (min-w-4) e i titoli lunghi vanno a capo invece di uscire dallo schermo */}
        <div className="flex-1 min-w-4"><FlourishDivider /></div>
        <span className="min-w-0 flex items-center justify-center gap-1.5 px-2 text-center text-xs font-cinzel font-bold uppercase tracking-[0.25em] max-xs:tracking-[0.15em] text-dnd-gold">
          {icon && <span className="shrink-0">{icon}</span>}
          <span>{children}</span>
        </span>
        <div className="flex-1 min-w-4"><FlourishDivider /></div>
      </div>
    )
  }
  return (
    <div className={`flex items-center gap-2 mt-4 mb-2 ${className}`}>
      <span className="min-w-0 flex items-center gap-1.5 text-xs font-cinzel font-bold text-dnd-gold uppercase tracking-[0.25em] max-xs:tracking-[0.15em] xs:whitespace-nowrap xs:shrink-0">
        {icon}
        {children}
      </span>
      <div className="flex-1 text-dnd-gold-dim">
        <FlourishDivider />
      </div>
    </div>
  )
}

const SectionDivider = React.memo(SectionDividerInner)
export default SectionDivider

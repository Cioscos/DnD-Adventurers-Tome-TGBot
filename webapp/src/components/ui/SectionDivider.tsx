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
        <FlourishDivider />
        <span className="shrink-0 flex items-center gap-1.5 px-2 text-[10px] font-cinzel font-bold uppercase tracking-[0.25em] text-dnd-gold">
          {icon}
          {children}
        </span>
        <FlourishDivider />
      </div>
    )
  }
  return (
    <div className={`flex items-center gap-2 mt-4 mb-2 ${className}`}>
      <span className="flex items-center gap-1.5 text-[10px] font-cinzel font-bold text-dnd-gold uppercase tracking-[0.25em] whitespace-nowrap shrink-0">
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

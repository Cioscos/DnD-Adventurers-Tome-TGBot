import React from 'react'

interface SectionHeaderProps {
  children: React.ReactNode
}

function SectionHeaderInner({ children }: SectionHeaderProps) {
  return (
    <div className="flex items-center gap-2 mt-4 mb-2">
      <span className="text-xs font-cinzel font-bold text-dnd-gold-dim uppercase tracking-widest whitespace-nowrap">
        {children}
      </span>
      <div className="flex-1 h-px bg-gradient-to-r from-dnd-gold-dim to-transparent" />
    </div>
  )
}

const SectionHeader = React.memo(SectionHeaderInner)
export default SectionHeader

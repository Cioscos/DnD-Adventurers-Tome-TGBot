import React from 'react'
import { LEDGER_TITLE } from '@/styles/ledger'

interface SectionDividerProps {
  children: React.ReactNode
  icon?: React.ReactNode
  align?: 'left' | 'center'
  className?: string
}

/** Titolo di sezione: etichetta semplice su un filetto, senza ornamenti (DESIGN.md, "Ledger Rows"). */
function SectionDividerInner({ children, icon, align = 'left', className = '' }: SectionDividerProps) {
  return (
    <h2 className={`mt-4 mb-1 flex items-center gap-1.5 border-b border-dnd-border pb-1 pl-1 ${align === 'center' ? 'justify-center text-center' : ''} ${LEDGER_TITLE} ${className}`}>
      {icon && <span className="shrink-0">{icon}</span>}
      <span className="min-w-0">{children}</span>
    </h2>
  )
}

const SectionDivider = React.memo(SectionDividerInner)
export default SectionDivider

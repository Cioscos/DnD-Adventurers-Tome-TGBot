import { type ReactNode } from 'react'

/** Una riga della barra filtri: etichetta della dimensione + chip scrollabili
 *  orizzontalmente (scrollbar nascosta, come ClassTabs / breadcrumb del Layout).
 *  Condivisa fra Abilità speciali e Incantesimi. */
export default function FilterRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-1">
      <span className="block px-1 text-[11px] font-cinzel uppercase tracking-widest text-dnd-gold-dim">
        {label}
      </span>
      <div className="flex gap-2 overflow-x-auto scrollbar-hide touch-pan-x pb-0.5">
        {children}
      </div>
    </div>
  )
}

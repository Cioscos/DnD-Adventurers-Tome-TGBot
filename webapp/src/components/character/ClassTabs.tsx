import { m } from 'framer-motion'

interface ClassEntry {
  class_name: string
  level: number
}

interface Props {
  classes: ClassEntry[]
  selected: string
  onSelect: (className: string) => void
}

export default function ClassTabs({ classes, selected, onSelect }: Props) {
  if (classes.length <= 1) return null
  return (
    <div role="tablist" className="flex gap-1 overflow-x-auto scrollbar-hide mb-2">
      {classes.map((c) => {
        const isActive = c.class_name === selected
        return (
          <m.button
            key={c.class_name}
            role="tab"
            aria-selected={isActive}
            type="button"
            onClick={() => onSelect(c.class_name)}
            whileTap={{ scale: 0.96 }}
            className={`shrink-0 px-3 py-1.5 rounded-full border text-xs font-cinzel uppercase tracking-wider transition-colors ${
              isActive
                ? 'bg-dnd-gold/20 border-dnd-gold text-dnd-gold-bright'
                : 'bg-dnd-surface border-dnd-gold-dim/30 text-dnd-text-muted'
            }`}
          >
            {c.class_name}
            <span className="ml-1 opacity-70">L{c.level}</span>
          </m.button>
        )
      })}
    </div>
  )
}

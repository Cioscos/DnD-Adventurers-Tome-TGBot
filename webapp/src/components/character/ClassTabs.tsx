import { useTranslation } from 'react-i18next'
import Pressable from '@/components/ui/Pressable'

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
  const { t } = useTranslation()
  if (classes.length <= 1) return null
  return (
    <div role="tablist" className="@container flex gap-1 overflow-x-auto scrollbar-hide mb-2">
      {classes.map((c) => {
        const isActive = c.class_name === selected
        return (
          <Pressable
            key={c.class_name}
            role="tab"
            aria-selected={isActive}
            type="button"
            onClick={() => onSelect(c.class_name)}
            whileTap={{ scale: 0.96 }}
            className={`shrink-0 min-h-[44px] inline-flex items-center px-3 @max-[360px]:px-2 py-1.5 rounded-full border text-xs @max-[360px]:text-[10px] font-cinzel uppercase tracking-wider transition-colors ${
              isActive
                ? 'bg-dnd-gold/20 border-dnd-gold text-dnd-gold-bright'
                : 'bg-dnd-surface border-dnd-gold-dim/30 text-dnd-text-muted'
            }`}
          >
            {t(`dnd.classes.${c.class_name}`, { defaultValue: c.class_name })}
            <span className="ml-1 opacity-70">L{c.level}</span>
          </Pressable>
        )
      })}
    </div>
  )
}

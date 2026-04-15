import { useTranslation } from 'react-i18next'
import DndButton from '@/components/DndButton'

interface SpellFilterProps {
  search: string
  onSearchChange: (value: string) => void
  onAddClick: () => void
}

export default function SpellFilter({ search, onSearchChange, onAddClick }: SpellFilterProps) {
  const { t } = useTranslation()

  return (
    <div className="flex gap-2">
      <input
        type="text"
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
        placeholder={t('character.spells.search')}
        className="flex-1 bg-dnd-surface rounded-xl px-3 py-2 outline-none text-dnd-text
                   placeholder:text-dnd-text-secondary/50
                   focus:ring-2 focus:ring-dnd-gold border border-transparent
                   focus:border-dnd-gold-dim"
      />
      <DndButton onClick={onAddClick} className="!px-4 !py-2">
        +
      </DndButton>
    </div>
  )
}

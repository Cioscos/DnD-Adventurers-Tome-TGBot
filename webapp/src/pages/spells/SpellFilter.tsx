import { useTranslation } from 'react-i18next'
import { Search, Plus, X } from 'lucide-react'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'

interface SpellFilterProps {
  search: string
  onSearchChange: (value: string) => void
  onAddClick: () => void
}

export default function SpellFilter({ search, onSearchChange, onAddClick }: SpellFilterProps) {
  const { t } = useTranslation()

  return (
    <div className="flex gap-2 items-end">
      {/* Tastiera "cerca" + X per svuotare (stesso pattern della Cronologia). */}
      <Input
        type="search"
        value={search}
        onChange={onSearchChange}
        placeholder={t('character.spells.search')}
        leadingIcon={<Search size={16} />}
        enterKeyHint="search"
        trailingAction={
          search ? (
            <Pressable
              onClick={() => onSearchChange('')}
              className="w-10 h-10 rounded-full flex items-center justify-center text-dnd-text-faint hover:text-dnd-gold-bright"
              aria-label={t('common.cancel')}
            >
              <X size={14} />
            </Pressable>
          ) : undefined
        }
        className="flex-1"
      />
      <Button variant="primary" size="md" onClick={onAddClick} icon={<Plus size={18} />} haptic="light" />
    </div>
  )
}

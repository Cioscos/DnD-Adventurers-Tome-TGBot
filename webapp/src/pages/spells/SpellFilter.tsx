import { useTranslation } from 'react-i18next'
import { Search, Plus } from 'lucide-react'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'

interface SpellFilterProps {
  search: string
  onSearchChange: (value: string) => void
  onAddClick: () => void
}

export default function SpellFilter({ search, onSearchChange, onAddClick }: SpellFilterProps) {
  const { t } = useTranslation()

  return (
    <div className="flex gap-2 items-end">
      <Input
        value={search}
        onChange={onSearchChange}
        placeholder={t('character.spells.search')}
        leadingIcon={<Search size={16} />}
        className="flex-1"
      />
      <Button variant="primary" size="md" onClick={onAddClick} icon={<Plus size={18} />} haptic="light" />
    </div>
  )
}

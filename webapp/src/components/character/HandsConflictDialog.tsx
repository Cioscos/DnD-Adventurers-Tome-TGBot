import { useTranslation } from 'react-i18next'
import { AlertTriangle } from 'lucide-react'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import type { Item } from '@/types'

interface Props {
  newItem: Item
  removedItem: Item
  pending?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export default function HandsConflictDialog({ newItem, removedItem, pending, onConfirm, onCancel }: Props) {
  const { t } = useTranslation()
  return (
    <Sheet open onClose={onCancel} centered title={t('character.equipment.hands_conflict.title')}>
      <div className="p-5 space-y-4">
        <div className="flex justify-center">
          <span className="w-12 h-12 rounded-full flex items-center justify-center border text-[var(--dnd-amber)] border-[color:var(--dnd-amber)]/50 bg-[color:var(--dnd-amber)]/15">
            <AlertTriangle size={22} />
          </span>
        </div>
        <p className="text-sm text-center text-dnd-text font-body">
          {t('character.equipment.hands_conflict.body', { newItem: newItem.name, removedItem: removedItem.name })}
        </p>
        <div className="flex gap-2">
          <Button variant="primary" fullWidth onClick={onCancel}>
            {t('common.cancel')}
          </Button>
          <Button
            variant="secondary"
            fullWidth
            onClick={onConfirm}
            loading={pending}
            haptic="warning"
            className="!text-[var(--dnd-amber)] !border-[color:var(--dnd-amber)]/55"
          >
            {t('character.equipment.hands_conflict.confirm')}
          </Button>
        </div>
      </div>
    </Sheet>
  )
}

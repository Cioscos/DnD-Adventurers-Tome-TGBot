import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import type { EquipmentSlot, Item, CharacterFull } from '@/types'

interface Props {
  charId: number
  slot: EquipmentSlot
  item: Item
  onClose: () => void
  onReplace: () => void
  onDetails: (item: Item) => void
}

export default function SlotActionSheet({ charId, slot, item, onClose, onReplace, onDetails }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()

  const unequip = useMutation({
    mutationFn: () =>
      api.items.update(charId, item.id, { is_equipped: false, equipment_slot: null }),
    onSuccess: (updated: CharacterFull) => {
      qc.setQueryData(['character', charId], updated)
      haptic.light()
      onClose()
    },
  })

  const slotLabel = t(`character.equipment.slots.${slot}`, { defaultValue: slot })

  return (
    <AnimatePresence>
      <m.div
        className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 backdrop-blur-sm"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <m.div
          className="w-full max-w-md bg-dnd-surface-raised border border-dnd-gold rounded-t-2xl pb-safe"
          initial={{ y: 100 }}
          animate={{ y: 0 }}
          exit={{ y: 100 }}
          transition={{ type: 'spring', stiffness: 260, damping: 28 }}
          onClick={(e) => e.stopPropagation()}
        >
          <header className="px-4 py-3 border-b border-dnd-gold-dim/40">
            <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim">{slotLabel}</p>
            <h2 className="text-sm font-bold text-dnd-gold-bright">{item.name}</h2>
          </header>
          <div className="flex flex-col">
            <button
              type="button"
              onClick={() => onDetails(item)}
              className="px-4 py-3 text-left hover:bg-dnd-surface text-dnd-text"
            >
              {t('character.equipment.actions.details', { defaultValue: 'Details' })}
            </button>
            <button
              type="button"
              onClick={onReplace}
              className="px-4 py-3 text-left hover:bg-dnd-surface text-dnd-text"
            >
              {t('character.equipment.actions.replace', { defaultValue: 'Replace' })}
            </button>
            <button
              type="button"
              onClick={() => unequip.mutate()}
              disabled={unequip.isPending}
              className="px-4 py-3 text-left hover:bg-dnd-surface text-[var(--dnd-crimson-bright)]"
            >
              {t('character.equipment.actions.unequip', { defaultValue: 'Unequip' })}
            </button>
          </div>
        </m.div>
      </m.div>
    </AnimatePresence>
  )
}

import { createPortal } from 'react-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { useRegisterOverlay } from '@/store/overlayStore'
import { useOverlayDismiss } from '@/hooks/useOverlayDismiss'
import Pressable from '@/components/ui/Pressable'
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
  useRegisterOverlay(true)
  // Overlay custom non-Sheet: ESC e back/BackButton chiudono (nota batch B1).
  useOverlayDismiss(true, onClose)

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
  const itemBtnCls =
    'min-h-[48px] px-4 py-3 text-left text-sm hover:bg-dnd-surface focus-visible:outline-none focus-visible:bg-dnd-surface focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-dnd-gold transition-colors'

  return createPortal(
    <AnimatePresence>
      <m.div
        className="fixed inset-0 z-50 flex items-end justify-center backdrop-blur-sm"
        style={{ background: 'var(--dnd-overlay)' }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <m.div
          className="w-full max-w-md bg-dnd-surface-raised border border-dnd-gold-dim/50 rounded-t-2xl pb-safe"
          initial={{ y: 100 }}
          animate={{ y: 0 }}
          exit={{ y: 100 }}
          transition={{ type: 'spring', stiffness: 260, damping: 28 }}
          onClick={(e) => e.stopPropagation()}
        >
          <header className="px-4 py-3 border-b border-dnd-border">
            <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim">{slotLabel}</p>
            <h2 className="text-sm font-bold text-dnd-gold-bright">{item.name}</h2>
          </header>
          <div className="flex flex-col">
            <Pressable type="button" onClick={() => onDetails(item)} className={`${itemBtnCls} text-dnd-text`}>
              {t('character.equipment.actions.details', { defaultValue: 'Details' })}
            </Pressable>
            <Pressable type="button" onClick={onReplace} className={`${itemBtnCls} text-dnd-text`}>
              {t('character.equipment.actions.replace', { defaultValue: 'Replace' })}
            </Pressable>
            <Pressable
              type="button"
              onClick={() => unequip.mutate()}
              pending={unequip.isPending}
              className={`${itemBtnCls} text-dnd-crimson-bright disabled:opacity-60`}
            >
              {t('character.equipment.actions.unequip', { defaultValue: 'Unequip' })}
            </Pressable>
          </div>
        </m.div>
      </m.div>
    </AnimatePresence>,
    document.body,
  )
}

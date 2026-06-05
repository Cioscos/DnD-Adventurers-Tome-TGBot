import { useState } from 'react'
import { createPortal } from 'react-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { X, Package } from 'lucide-react'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { ITEM_TYPE_TO_SLOTS, handsConflict } from '@/lib/equipmentSlots'
import { useRegisterOverlay } from '@/store/overlayStore'
import type { EquipmentSlot, Item, CharacterFull } from '@/types'
import { useUnitSettings, formatWeight } from '@/store/unitSettings'
import HandsConflictDialog from './HandsConflictDialog'

interface Props {
  charId: number
  slot: EquipmentSlot
  items: Item[]
  onClose: () => void
}

function compatibleItems(items: Item[], slot: EquipmentSlot): Item[] {
  return items.filter((i) => {
    const allowed = ITEM_TYPE_TO_SLOTS[i.item_type] ?? []
    return allowed.includes(slot)
  })
}

export default function EquipItemPicker({ charId, slot, items, onClose }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const navigate = useNavigate()
  useRegisterOverlay(true)
  const system = useUnitSettings((s) => s.system)

  const [conflict, setConflict] = useState<{ newItem: Item; removedItem: Item } | null>(null)

  const equip = useMutation({
    mutationFn: async ({ itemId, removeId }: { itemId: number; removeId?: number }) => {
      if (removeId != null) {
        await api.items.update(charId, removeId, { is_equipped: false, equipment_slot: null })
      }
      return api.items.update(charId, itemId, { is_equipped: true, equipment_slot: slot })
    },
    onSuccess: (updated: CharacterFull) => {
      qc.setQueryData(['character', charId], updated)
      haptic.light()
      setConflict(null)
      onClose()
    },
  })

  const handlePick = (it: Item) => {
    const c = handsConflict(items, it, slot)
    if (c) {
      setConflict({ newItem: it, removedItem: c })
      return
    }
    equip.mutate({ itemId: it.id })
  }

  const candidates = compatibleItems(items, slot)
  const slotLabel = t(`character.equipment.slots.${slot}`, { defaultValue: slot })

  return createPortal(
    <AnimatePresence>
      <m.div
        className="fixed inset-0 z-50 flex items-end sm:items-center justify-center backdrop-blur-sm"
        style={{ background: 'var(--dnd-overlay)' }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <m.div
          className="@container w-full max-w-md max-h-[85vh] overflow-y-auto bg-dnd-surface-raised border border-dnd-gold-dim/50 rounded-t-2xl sm:rounded-2xl"
          initial={{ y: 40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 40, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
        >
          <header className="flex items-center justify-between px-4 py-3 border-b border-dnd-border">
            <h2 className="text-sm font-cinzel uppercase tracking-widest text-dnd-gold-bright">
              {t('character.equipment.picker.title', { defaultValue: 'Equip' })}: {slotLabel}
            </h2>
            <button
              type="button"
              onClick={onClose}
              aria-label={t('common.close', { defaultValue: 'Close' })}
              className="w-11 h-11 flex items-center justify-center rounded-full border border-dnd-border hover:border-dnd-gold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-dnd-gold focus-visible:ring-offset-2 focus-visible:ring-offset-dnd-surface-raised transition-colors"
            >
              <X size={18} className="text-dnd-text-muted" />
            </button>
          </header>
          {candidates.length === 0 ? (
            <div className="p-6 text-center space-y-3">
              <p className="text-sm text-dnd-text-faint italic">
                {t('character.equipment.picker.empty', { defaultValue: 'No compatible items in inventory.' })}
              </p>
              <button
                type="button"
                onClick={() => { onClose(); navigate(`/char/${charId}/inventory`) }}
                className="inline-flex items-center gap-2 min-h-[44px] px-4 rounded-full bg-dnd-surface border border-dnd-gold-dim/60 hover:border-dnd-gold text-dnd-gold-bright font-cinzel text-[11px] uppercase tracking-widest transition-colors"
              >
                <Package size={14} aria-hidden="true" />
                {t('character.equipment.picker.go_to_inventory', { defaultValue: 'Open inventory' })}
              </button>
            </div>
          ) : (
            <ul className="divide-y divide-dnd-border/60">
              {candidates.map((it) => {
                const initial = it.name?.trim()?.[0]?.toUpperCase() ?? ''
                return (
                  <li key={it.id}>
                    <button
                      type="button"
                      onClick={() => handlePick(it)}
                      disabled={equip.isPending}
                      className="w-full text-left px-4 py-3 hover:bg-dnd-surface focus-visible:outline-none focus-visible:bg-dnd-surface focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-dnd-gold flex items-center gap-3 disabled:opacity-60"
                    >
                      <m.span
                        layoutId={`equip-icon-${it.id}`}
                        className="shrink-0 w-9 h-9 rounded-md border border-dnd-gold-dim/60 bg-dnd-surface flex items-center justify-center font-cinzel font-bold text-base text-dnd-gold-bright"
                        aria-hidden="true"
                      >
                        {initial}
                      </m.span>
                      <span className="flex flex-col gap-0.5 min-w-0 flex-1">
                        <span className="text-sm font-bold text-dnd-text">{it.name}</span>
                        <span className="text-[11px] text-dnd-text-muted break-words">
                          {it.item_type} · {formatWeight(it.weight, system)}
                        </span>
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </m.div>
      </m.div>
      {conflict && (
        <HandsConflictDialog
          newItem={conflict.newItem}
          removedItem={conflict.removedItem}
          pending={equip.isPending}
          onCancel={() => setConflict(null)}
          onConfirm={() => equip.mutate({ itemId: conflict.newItem.id, removeId: conflict.removedItem.id })}
        />
      )}
    </AnimatePresence>,
    document.body,
  )
}

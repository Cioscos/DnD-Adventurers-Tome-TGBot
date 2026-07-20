import { useState } from 'react'
import { createPortal } from 'react-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { X, Package } from 'lucide-react'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import Pressable from '@/components/ui/Pressable'
import { ITEM_TYPE_TO_SLOTS, handsConflict } from '@/lib/equipmentSlots'
import { useRegisterOverlay } from '@/store/overlayStore'
import { useOverlayDismiss } from '@/hooks/useOverlayDismiss'
import { useDeferredBlur } from '@/hooks/useDeferredBlur'
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
  // Overlay custom non-Sheet: ESC e back/BackButton chiudono (nota batch B1).
  useOverlayDismiss(true, onClose)
  // Il genitore smonta questo componente con un semplice `{cond && <.../>}`
  // (nessuna AnimatePresence esterna): l'exit dichiarato sotto non viene mai
  // giocato, quindi "visible" per il blur differito è costante true finché
  // il componente esiste.
  const { blurStyle, onEntranceComplete } = useDeferredBlur(true, 4)
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

  type FacetKey = 'weapon_type' | 'damage_type' | 'properties'
  const meta = (it: Item) => (it.item_metadata ?? {}) as Record<string, unknown>
  const weaponCandidates = candidates.filter((c) => c.item_type === 'weapon')

  const facetValues: Record<FacetKey, string[]> = {
    weapon_type: [...new Set(weaponCandidates.map((c) => meta(c).weapon_type).filter(Boolean) as string[])],
    damage_type: [...new Set(weaponCandidates.map((c) => meta(c).damage_type).filter(Boolean) as string[])],
    properties: [...new Set(weaponCandidates.flatMap((c) => (Array.isArray(meta(c).properties) ? (meta(c).properties as string[]) : [])))],
  }

  const [filters, setFilters] = useState<Record<FacetKey, Set<string>>>({
    weapon_type: new Set(), damage_type: new Set(), properties: new Set(),
  })
  const toggleFilter = (key: FacetKey, val: string) =>
    setFilters((f) => {
      const next = new Set(f[key])
      if (next.has(val)) next.delete(val)
      else next.add(val)
      return { ...f, [key]: next }
    })

  const passes = (it: Item): boolean => {
    if (it.item_type !== 'weapon') return true // scudi ecc. passano sempre
    const m = meta(it)
    if (filters.weapon_type.size && !filters.weapon_type.has(String(m.weapon_type))) return false
    if (filters.damage_type.size && !filters.damage_type.has(String(m.damage_type))) return false
    if (filters.properties.size) {
      const props = Array.isArray(m.properties) ? (m.properties as string[]) : []
      if (!props.some((p) => filters.properties.has(p))) return false
    }
    return true
  }
  const visible = candidates.filter(passes)

  const facetLabelKey: Record<FacetKey, string> = {
    weapon_type: 'character.equipment.filters.weapon_type',
    damage_type: 'character.equipment.filters.damage',
    properties: 'character.equipment.filters.properties',
  }
  const chipLabel = (key: FacetKey, v: string) =>
    key === 'weapon_type' ? t(`character.inventory.weapon_type.${v}`)
    : key === 'damage_type' ? t(`character.inventory.damage_types.${v}`)
    : t(`character.inventory.weapon_properties.${v}`)
  const shownFacets = (Object.keys(facetValues) as FacetKey[]).filter((k) => facetValues[k].length >= 2)

  const slotLabel = t(`character.equipment.slots.${slot}`, { defaultValue: slot })

  return createPortal(
    <>
      <AnimatePresence>
      <m.div
        className="fixed inset-0 z-50 flex items-end sm:items-center justify-center"
        style={{ background: 'var(--dnd-overlay)', ...blurStyle }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onAnimationComplete={onEntranceComplete}
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
            <Pressable
              type="button"
              onClick={onClose}
              aria-label={t('common.close', { defaultValue: 'Close' })}
              className="w-11 h-11 flex items-center justify-center rounded-full border border-dnd-border hover:border-dnd-gold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-dnd-gold focus-visible:ring-offset-2 focus-visible:ring-offset-dnd-surface-raised transition-colors"
            >
              <X size={18} className="text-dnd-text-muted" />
            </Pressable>
          </header>
          {shownFacets.length > 0 && (
            <div className="px-4 py-3 border-b border-dnd-border bg-dnd-surface space-y-2">
              {shownFacets.map((key) => (
                <div key={key}>
                  <p className="text-[9px] font-cinzel uppercase tracking-widest text-dnd-gold-dim mb-1">
                    {t(facetLabelKey[key])}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {facetValues[key].map((v) => {
                      const on = filters[key].has(v)
                      return (
                        <Pressable
                          key={v}
                          type="button"
                          onClick={() => toggleFilter(key, v)}
                          className={`px-2.5 py-1.5 rounded-full text-[11px] font-medium transition-colors
                            ${on ? 'bg-dnd-gold text-dnd-ink shadow-halo-gold' : 'bg-dnd-surface-raised text-dnd-text border border-dnd-border'}`}
                        >
                          {chipLabel(key, v)}
                        </Pressable>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
          {visible.length === 0 ? (
            <div className="p-6 text-center space-y-3">
              <p className="text-sm text-dnd-text-faint italic">
                {t('character.equipment.picker.empty', { defaultValue: 'No compatible items in inventory.' })}
              </p>
              <Pressable
                type="button"
                onClick={() => { onClose(); navigate(`/char/${charId}/inventory`) }}
                className="inline-flex items-center gap-2 min-h-[44px] px-4 rounded-full bg-dnd-surface border border-dnd-gold-dim/60 hover:border-dnd-gold text-dnd-gold-bright font-cinzel text-[11px] uppercase tracking-widest transition-colors"
              >
                <Package size={14} aria-hidden="true" />
                {t('character.equipment.picker.go_to_inventory', { defaultValue: 'Open inventory' })}
              </Pressable>
            </div>
          ) : (
            <ul className="divide-y divide-dnd-border/60">
              {visible.map((it) => {
                const initial = it.name?.trim()?.[0]?.toUpperCase() ?? ''
                return (
                  <li key={it.id}>
                    <Pressable
                      type="button"
                      onClick={() => handlePick(it)}
                      pending={equip.isPending && equip.variables?.itemId === it.id}
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
                          {t(`character.inventory.types.${it.item_type}`, { defaultValue: it.item_type })} · {formatWeight(it.weight, system)}
                        </span>
                      </span>
                    </Pressable>
                  </li>
                )
              })}
            </ul>
          )}
        </m.div>
      </m.div>
      </AnimatePresence>
      {/* Fuori da AnimatePresence: è uno Sheet con portal e animazioni proprie
          (due figli anonimi nella stessa AnimatePresence = warning di chiavi
          duplicate React). */}
      {conflict && (
        <HandsConflictDialog
          newItem={conflict.newItem}
          removedItem={conflict.removedItem}
          pending={equip.isPending}
          onCancel={() => setConflict(null)}
          onConfirm={() => equip.mutate({ itemId: conflict.newItem.id, removeId: conflict.removedItem.id })}
        />
      )}
    </>,
    document.body,
  )
}

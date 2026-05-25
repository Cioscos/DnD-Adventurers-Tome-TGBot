import { useState, useCallback, useEffect, useRef } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useToast } from '@/hooks/useToast'
import { m, AnimatePresence } from 'framer-motion'
import { Plus, Weight, ChevronRight } from 'lucide-react'
import { GiKnapsack as Backpack } from 'react-icons/gi'
import { api, ApiError } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Sheet from '@/components/ui/Sheet'
import { slotsAllowedFor, SLOT_PLACEHOLDER_ICON } from '@/lib/equipmentSlots'
import type { EquipmentSlot } from '@/types'
import ScrollArea from '@/components/ScrollArea'
import EmptyState from '@/components/ui/EmptyState'
import ProgressTriad from '@/components/ui/ProgressTriad'
import WeaponAttackModal, { type WeaponAttackResult } from '@/components/WeaponAttackModal'
import { haptic } from '@/auth/telegram'
import InventoryItem from '@/pages/inventory/InventoryItem'
import ItemForm from '@/pages/inventory/ItemForm'
import { buildItemMetadata, type ItemFormData } from '@/pages/inventory/itemMetadata'
import { getItemTypeIcon } from '@/lib/itemIcons'
import type { Item } from '@/types'

export default function Inventory() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const location = useLocation()
  const navigate = useNavigate()
  const initialHighlight =
    typeof (location.state as { highlightItemId?: unknown } | null)?.highlightItemId === 'number'
      ? ((location.state as { highlightItemId: number }).highlightItemId)
      : null
  const [highlightId, setHighlightId] = useState<number | null>(initialHighlight)
  const itemRefs = useRef<Record<number, HTMLDivElement | null>>({})
  const { t } = useTranslation()
  const qc = useQueryClient()

  const [showAdd, setShowAdd] = useState(false)
  const [editingItem, setEditingItem] = useState<Item | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null)
  type AttackState = {
    result: WeaponAttackResult
    itemId: number
    wasRerolled: boolean
  }
  const [attackState, setAttackState] = useState<AttackState | null>(null)
  const [slotPickerItem, setSlotPickerItem] = useState<Item | null>(null)
  const toast = useToast()
  const [expanded, setExpanded] = useState<number | null>(null)
  const [collapsedTypes, setCollapsedTypes] = useState<Set<string>>(new Set())

  const toggleType = (type: string) => {
    setCollapsedTypes((prev) => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const addMutation = useMutation({
    mutationFn: (form: ItemFormData) =>
      api.items.add(charId, {
        name: form.name.trim(),
        item_type: form.item_type,
        quantity: Number(form.quantity) || 1,
        weight: Number(form.weight) || 0,
        description: form.description.trim() || undefined,
        is_equipped: false,
        item_metadata: buildItemMetadata(form),
      }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setShowAdd(false)
      setEditingItem(null)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const updateMutation = useMutation({
    mutationFn: ({ itemId, form }: { itemId: number; form: ItemFormData }) =>
      api.items.update(charId, itemId, {
        name: form.name.trim(),
        item_type: form.item_type,
        quantity: Number(form.quantity) || 1,
        weight: Number(form.weight) || 0,
        description: form.description.trim() || undefined,
        item_metadata: buildItemMetadata(form),
      }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setShowAdd(false)
      setEditingItem(null)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const toggleEquip = useMutation({
    mutationFn: ({ itemId, equipped, slot }: { itemId: number; equipped: boolean; slot?: EquipmentSlot }) =>
      api.items.update(charId, itemId, slot
        ? { is_equipped: equipped, equipment_slot: slot }
        : { is_equipped: equipped }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setSlotPickerItem(null)
    },
  })

  const handleEquipToggle = (item: Item) => {
    if (item.is_equipped) {
      toggleEquip.mutate({ itemId: item.id, equipped: false })
      return
    }
    const allowedSlots = slotsAllowedFor(item.item_type)
    if (allowedSlots.length > 1) {
      setSlotPickerItem(item)
      return
    }
    // Single allowed slot: auto-assign so AC bridge (ArmorClass.tsx) and
    // PaperDoll can detect the item; backend does not auto-fill the slot.
    toggleEquip.mutate({
      itemId: item.id,
      equipped: true,
      slot: allowedSlots.length === 1 ? allowedSlots[0] : undefined,
    })
  }

  const updateQty = useMutation({
    mutationFn: ({ itemId, quantity }: { itemId: number; quantity: number }) =>
      api.items.update(charId, itemId, { quantity: Math.max(0, quantity) }),
    onSuccess: (updated) => qc.setQueryData(['character', charId], updated),
  })

  const deleteMutation = useMutation({
    mutationFn: (itemId: number) => api.items.remove(charId, itemId),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setDeleteTarget(null)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const attackMutation = useMutation({
    mutationFn: (itemId: number) => api.items.attack(charId, itemId),
    onSuccess: (result, itemId) => {
      setAttackState({ result, itemId, wasRerolled: false })
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const attackRerollMutation = useMutation({
    mutationFn: (itemId: number) => api.items.attack(charId, itemId, true),
    onSuccess: (result) => {
      setAttackState((prev) => prev && { ...prev, result, wasRerolled: true })
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.success()
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) {
        toast.error(t('character.inspiration.unavailable_error'))
        qc.invalidateQueries({ queryKey: ['character', charId] })
      } else {
        haptic.error()
      }
    },
  })

  const handleFormSubmit = useCallback((data: ItemFormData) => {
    if (editingItem) {
      updateMutation.mutate({ itemId: editingItem.id, form: data })
    } else {
      addMutation.mutate(data)
    }
  }, [editingItem, updateMutation, addMutation])

  const handleFormCancel = useCallback(() => {
    setShowAdd(false)
    setEditingItem(null)
  }, [])

  const handleEdit = useCallback((item: Item) => {
    setEditingItem(item)
    setShowAdd(true)
  }, [])

  useEffect(() => {
    if (highlightId === null) return
    if (!char) return // attendi che la character query carichi
    const target = char.items?.find((i) => i.id === highlightId)
    if (!target) {
      setHighlightId(null)
      navigate(location.pathname, { replace: true, state: null })
      return
    }

    // Espandi l'item
    setExpanded(highlightId)

    // Sblocca il tipo collassato (se serve)
    const TYPE_ORDER = ['weapon', 'armor', 'shield', 'consumable', 'tool', 'accessory', 'gear', 'potion', 'scroll', 'generic']
    const typeKey = TYPE_ORDER.includes(target.item_type) ? target.item_type : 'generic'
    setCollapsedTypes((prev) => {
      if (!prev.has(typeKey)) return prev
      const next = new Set(prev)
      next.delete(typeKey)
      return next
    })

    // Scroll into view (dopo il prossimo frame, così il DOM ha avuto tempo di espandere)
    const rafId = requestAnimationFrame(() => {
      itemRefs.current[highlightId]?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    })

    // Fade dopo 3s e clear della state
    const tid = window.setTimeout(() => {
      setHighlightId(null)
      navigate(location.pathname, { replace: true, state: null })
    }, 3000)

    return () => {
      cancelAnimationFrame(rafId)
      window.clearTimeout(tid)
    }
  }, [highlightId, char, navigate, location.pathname])

  if (!char) return null

  const items: Item[] = char.items ?? []
  const totalWeight = items.reduce((sum, i) => sum + i.weight * i.quantity, 0)

  const TYPE_ORDER: string[] = ['weapon', 'armor', 'shield', 'consumable', 'tool', 'accessory', 'gear', 'potion', 'scroll', 'generic']
  const grouped = items.reduce<Record<string, Item[]>>((acc, item) => {
    const key = TYPE_ORDER.includes(item.item_type) ? item.item_type : 'generic'
    if (!acc[key]) acc[key] = []
    acc[key].push(item)
    return acc
  }, {})
  for (const k of Object.keys(grouped)) {
    grouped[k].sort((a, b) => {
      if (a.is_equipped !== b.is_equipped) return a.is_equipped ? -1 : 1
      return a.name.localeCompare(b.name)
    })
  }
  const orderedTypes = TYPE_ORDER.filter((t) => grouped[t]?.length)

  return (
    <Layout title={t('character.inventory.title')} backTo={`/char/${charId}`} group="equipment" page="inventory">
      {/* Add button + carry capacity */}
      <div className="flex gap-2 items-end">
        <Button
          variant="primary"
          size="md"
          fullWidth
          onClick={() => setShowAdd(true)}
          icon={<Plus size={18} />}
          haptic="medium"
        >
          {t('character.inventory.add')}
        </Button>
      </div>

      {/* Carry capacity progress bar (Semantic Triad coloring) */}
      <Surface variant="elevated" className="!py-2">
        <div className="flex items-center gap-2 mb-1.5">
          <Weight size={13} className="text-dnd-gold-dim" />
          <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim flex-1">
            {t('character.inventory.carry_label')}
          </p>
        </div>
        <ProgressTriad
          value={totalWeight}
          max={char.carry_capacity}
          display={`${totalWeight.toFixed(1)} / ${char.carry_capacity} lb`}
          showNumeric
        />
      </Surface>

      {items.length === 0 && (
        <EmptyState
          icon={<Backpack size={32} />}
          title={t('common.none')}
          hint={t('character.inventory.empty_hint')}
          action={{
            label: t('character.inventory.add'),
            onClick: () => setShowAdd(true),
            icon: <Plus size={14} />,
          }}
        />
      )}

      <ScrollArea>
        {orderedTypes.map((type) => {
          const groupItems = grouped[type]
          const isCollapsed = collapsedTypes.has(type)
          const TypeIcon = getItemTypeIcon(type)
          return (
            <div key={type} className="mb-4">
              <m.button
                type="button"
                onClick={() => toggleType(type)}
                className="sticky top-0 z-[5] -mx-4 w-[calc(100%+2rem)] px-5 py-2 flex items-center gap-2 bg-dnd-bg/95 backdrop-blur-sm border-b border-dnd-border/40 text-left"
                aria-expanded={!isCollapsed}
              >
                <ChevronRight
                  size={14}
                  className={`text-dnd-gold-bright transition-transform ${!isCollapsed ? 'rotate-90' : ''}`}
                />
                <TypeIcon size={14} className="text-dnd-gold/80 shrink-0" />
                <span className="font-cinzel uppercase tracking-widest text-xs text-dnd-gold-bright flex-1">
                  {t(`character.inventory.types.${type}`)}
                </span>
                <span className="text-[10px] text-dnd-text-muted font-mono tabular-nums">
                  · {groupItems.length}
                </span>
              </m.button>
              <AnimatePresence>
                {!isCollapsed && (
                  <m.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="space-y-2 mt-2">
                      {groupItems.map((item) => (
                        <m.div
                          key={item.id}
                          layout
                          transition={{ duration: 0.18, ease: [0.25, 0.1, 0.25, 1] }}
                          ref={(el) => { itemRefs.current[item.id] = el }}
                          className={highlightId === item.id ? 'animate-pulse-glow' : undefined}
                        >
                          <InventoryItem
                            item={item}
                            isExpanded={expanded === item.id}
                            onToggle={() => setExpanded(expanded === item.id ? null : item.id)}
                            onEquipToggle={() => handleEquipToggle(item)}
                            onQuantityChange={(delta) => updateQty.mutate({ itemId: item.id, quantity: item.quantity + delta })}
                            onAttack={() => attackMutation.mutate(item.id)}
                            onEdit={() => handleEdit(item)}
                            onDelete={() => setDeleteTarget(item.id)}
                            equipPending={toggleEquip.isPending}
                            attackPending={attackMutation.isPending}
                          />
                        </m.div>
                      ))}
                    </div>
                  </m.div>
                )}
              </AnimatePresence>
            </div>
          )
        })}
      </ScrollArea>

      {showAdd && (
        <ItemForm
          initialData={editingItem}
          onSubmit={handleFormSubmit}
          onCancel={handleFormCancel}
          isPending={addMutation.isPending || updateMutation.isPending}
        />
      )}

      {attackState && (
        <WeaponAttackModal
          result={attackState.result}
          inspirationAvailable={Boolean(char?.heroic_inspiration)}
          isRerolling={attackRerollMutation.isPending}
          wasRerolled={attackState.wasRerolled}
          onInspirationReroll={() => attackRerollMutation.mutate(attackState.itemId)}
          onClose={() => setAttackState(null)}
        />
      )}

      {/* Delete confirmation as Sheet */}
      <Sheet
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        centered
        title={t('common.confirm')}
      >
        <div className="p-5 space-y-3">
          <p className="text-sm text-center text-dnd-text font-body">
            {t('character.select.delete_confirm', {
              name: items.find((i) => i.id === deleteTarget)?.name ?? '',
            })}
          </p>
          <div className="flex gap-2">
            <Button
              variant="danger"
              fullWidth
              onClick={() => deleteTarget !== null && deleteMutation.mutate(deleteTarget)}
              loading={deleteMutation.isPending}
              haptic="error"
            >
              {t('common.delete')}
            </Button>
            <Button variant="secondary" fullWidth onClick={() => setDeleteTarget(null)}>
              {t('common.cancel')}
            </Button>
          </div>
        </div>
      </Sheet>

      {/* Slot picker for multi-slot equippable items */}
      <Sheet
        open={slotPickerItem !== null}
        onClose={() => setSlotPickerItem(null)}
        centered
        title={t('character.equipment.slot_picker.title')}
      >
        {slotPickerItem && (
          <div className="p-5 space-y-4">
            <p className="text-sm text-center text-dnd-text-muted font-body">
              {t('character.equipment.slot_picker.subtitle', { name: slotPickerItem.name })}
            </p>
            <div className="grid grid-cols-2 gap-2">
              {slotsAllowedFor(slotPickerItem.item_type).map((slot) => {
                const Icon = SLOT_PLACEHOLDER_ICON[slot]
                return (
                  <m.button
                    key={slot}
                    onClick={() => toggleEquip.mutate({ itemId: slotPickerItem.id, equipped: true, slot })}
                    disabled={toggleEquip.isPending}
                    className="flex items-center gap-2 p-3 rounded-xl bg-dnd-surface border border-dnd-border hover:border-dnd-gold/60 disabled:opacity-50"
                    whileTap={{ scale: 0.96 }}
                  >
                    <Icon size={20} className="text-dnd-gold shrink-0" />
                    <span className="text-sm font-cinzel text-dnd-gold-bright">
                      {t(`character.equipment.slots.${slot}`)}
                    </span>
                  </m.button>
                )
              })}
            </div>
            <Button variant="secondary" fullWidth onClick={() => setSlotPickerItem(null)}>
              {t('common.cancel')}
            </Button>
          </div>
        )}
      </Sheet>

      <AnimatePresence />
    </Layout>
  )
}

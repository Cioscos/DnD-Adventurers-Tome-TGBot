import { useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { Plus, Weight, ChevronRight } from 'lucide-react'
import { GiKnapsack as Backpack } from 'react-icons/gi'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import StatPill from '@/components/ui/StatPill'
import Sheet from '@/components/ui/Sheet'
import ScrollArea from '@/components/ScrollArea'
import WeaponAttackModal, { type WeaponAttackResult } from '@/components/WeaponAttackModal'
import { haptic } from '@/auth/telegram'
import { spring } from '@/styles/motion'
import InventoryItem from '@/pages/inventory/InventoryItem'
import ItemForm from '@/pages/inventory/ItemForm'
import { buildItemMetadata, type ItemFormData } from '@/pages/inventory/itemMetadata'
import type { Item } from '@/types'

export default function Inventory() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()

  const [showAdd, setShowAdd] = useState(false)
  const [editingItem, setEditingItem] = useState<Item | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null)
  const [attackResult, setAttackResult] = useState<WeaponAttackResult | null>(null)
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
    mutationFn: ({ itemId, equipped }: { itemId: number; equipped: boolean }) =>
      api.items.update(charId, itemId, { is_equipped: equipped }),
    onSuccess: (updated) => qc.setQueryData(['character', charId], updated),
  })

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
    onSuccess: (result) => {
      setAttackResult(result)
      haptic.success()
    },
    onError: () => haptic.error(),
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

  if (!char) return null

  const items: Item[] = char.items ?? []
  const totalWeight = items.reduce((sum, i) => sum + i.weight * i.quantity, 0)
  const capacityPct = char.carry_capacity > 0 ? Math.min(100, (totalWeight / char.carry_capacity) * 100) : 0
  const overload = totalWeight > char.carry_capacity

  const TYPE_ORDER: string[] = ['weapon', 'armor', 'shield', 'consumable', 'tool', 'accessory', 'gear', 'potion', 'scroll', 'generic', 'other']
  const grouped = items.reduce<Record<string, Item[]>>((acc, item) => {
    const key = TYPE_ORDER.includes(item.item_type) ? item.item_type : 'other'
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

      {/* Carry capacity badge (no bar) */}
      <Surface variant="elevated" className="!py-2">
        <div className="flex items-center gap-2">
          <Weight size={13} className="text-dnd-gold-dim" />
          <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim flex-1">
            {t('character.inventory.carry_short', { defaultValue: 'Carico' })}
          </p>
          <StatPill
            tone={overload ? 'crimson' : capacityPct > 70 ? 'amber' : 'default'}
            size="sm"
            value={`${totalWeight.toFixed(1)}/${char.carry_capacity}`}
          />
        </div>
      </Surface>

      {items.length === 0 && (
        <Surface variant="flat" className="text-center py-8">
          <Backpack className="mx-auto text-dnd-text-faint mb-2" size={32} />
          <p className="text-dnd-text-muted font-body italic">{t('common.none')}</p>
        </Surface>
      )}

      <ScrollArea>
        {orderedTypes.map((type) => {
          const groupItems = grouped[type]
          const isCollapsed = collapsedTypes.has(type)
          return (
            <div key={type} className="mb-4">
              <m.button
                type="button"
                onClick={() => toggleType(type)}
                className="sticky z-[5] -mx-4 w-[calc(100%+2rem)] px-5 py-2 flex items-center gap-2 bg-dnd-bg/95 backdrop-blur-sm border-b border-dnd-border/40 text-left"
                style={{ top: '68px' }}
                aria-expanded={!isCollapsed}
              >
                <ChevronRight
                  size={14}
                  className={`text-dnd-gold-bright transition-transform ${!isCollapsed ? 'rotate-90' : ''}`}
                />
                <span className="font-cinzel uppercase tracking-widest text-xs text-dnd-gold-bright flex-1">
                  {t(`character.inventory.types.${type}`)}
                </span>
                <span className="text-[10px] text-dnd-text-muted font-mono">
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
                        <m.div key={item.id} layout transition={spring.drift}>
                          <InventoryItem
                            item={item}
                            isExpanded={expanded === item.id}
                            onToggle={() => setExpanded(expanded === item.id ? null : item.id)}
                            onEquipToggle={() => toggleEquip.mutate({ itemId: item.id, equipped: !item.is_equipped })}
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

      {attackResult && (
        <WeaponAttackModal result={attackResult} onClose={() => setAttackResult(null)} />
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

      <AnimatePresence />
    </Layout>
  )
}

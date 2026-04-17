import { useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { Plus, Backpack, Weight } from 'lucide-react'
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
  // Sort: equipped first, then alphabetical
  const sortedItems = [...items].sort((a, b) => {
    if (a.is_equipped !== b.is_equipped) return a.is_equipped ? -1 : 1
    return a.name.localeCompare(b.name)
  })
  const totalWeight = items.reduce((sum, i) => sum + i.weight * i.quantity, 0)
  const capacityPct = char.carry_capacity > 0 ? Math.min(100, (totalWeight / char.carry_capacity) * 100) : 0
  const overload = totalWeight > char.carry_capacity

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

      {/* Carry capacity gauge */}
      <Surface variant="elevated" className="!py-2.5">
        <div className="flex items-center gap-2 mb-1.5">
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
        <div className="h-1.5 rounded-full bg-dnd-ink/60 overflow-hidden">
          <m.div
            className={`h-full rounded-full ${
              overload
                ? 'bg-gradient-ember'
                : capacityPct > 70
                  ? 'bg-gradient-to-r from-dnd-amber to-dnd-gold-bright'
                  : 'bg-gradient-to-r from-dnd-emerald-deep to-dnd-emerald-bright'
            }`}
            initial={false}
            animate={{ width: `${capacityPct}%` }}
            transition={spring.drift}
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
        <div className="space-y-2">
          {sortedItems.map((item) => (
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

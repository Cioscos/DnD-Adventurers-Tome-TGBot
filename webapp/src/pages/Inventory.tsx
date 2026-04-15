import { useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import DndButton from '@/components/DndButton'
import ScrollArea from '@/components/ScrollArea'
import WeaponAttackModal, { type WeaponAttackResult } from '@/components/WeaponAttackModal'
import { haptic } from '@/auth/telegram'
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

  // --- Mutations ---

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

  // --- Callbacks ---

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

  // --- Derived ---

  if (!char) return null

  const items: Item[] = char.items ?? []
  const totalWeight = items.reduce((sum, i) => sum + i.weight * i.quantity, 0)

  return (
    <Layout title={t('character.inventory.title')} backTo={`/char/${charId}`} group="equipment" page="inventory">
      <div className="flex gap-2 items-center">
        <DndButton
          onClick={() => setShowAdd(true)}
          className="flex-1"
        >
          + {t('character.inventory.add')}
        </DndButton>
        <Card className="!py-2 !px-3">
          <p className="text-xs text-dnd-text-secondary">{t('character.inventory.carry', {
            enc: totalWeight.toFixed(1),
            cap: char.carry_capacity,
          })}</p>
        </Card>
      </div>

      {items.length === 0 && (
        <Card>
          <p className="text-center text-dnd-text-secondary">{t('common.none')}</p>
        </Card>
      )}

      <ScrollArea>
        <div className="space-y-2">
          {items.map((item) => (
            <InventoryItem
              key={item.id}
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
          ))}
        </div>
      </ScrollArea>

      {/* Add/Edit item form modal */}
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

      {deleteTarget !== null && (
        <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4">
          <Card variant="elevated" className="w-full space-y-3">
            <p className="text-sm text-center text-dnd-text">
              {t('character.select.delete_confirm', {
                name: items.find((i) => i.id === deleteTarget)?.name ?? '',
              })}
            </p>
            <div className="flex gap-2">
              <DndButton
                variant="danger"
                onClick={() => deleteMutation.mutate(deleteTarget)}
                loading={deleteMutation.isPending}
                className="flex-1"
              >
                {t('common.delete')}
              </DndButton>
              <DndButton
                variant="secondary"
                onClick={() => setDeleteTarget(null)}
                className="flex-1"
              >
                {t('common.cancel')}
              </DndButton>
            </div>
          </Card>
        </div>
      )}
    </Layout>
  )
}

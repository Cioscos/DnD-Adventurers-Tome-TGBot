import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import { haptic } from '@/auth/telegram'
import type { Item } from '@/types'

const ITEM_TYPES = ['weapon', 'armor', 'potion', 'scroll', 'tool', 'gear', 'other']

type AddForm = { name: string; item_type: string; quantity: string; weight: string; description: string }

const emptyForm: AddForm = { name: '', item_type: 'gear', quantity: '1', weight: '0', description: '' }

export default function Inventory() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState<AddForm>(emptyForm)
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const addMutation = useMutation({
    mutationFn: () =>
      api.items.add(charId, {
        name: form.name.trim(),
        item_type: form.item_type,
        quantity: Number(form.quantity) || 1,
        weight: Number(form.weight) || 0,
        description: form.description.trim() || undefined,
        is_equipped: false,
      }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      setShowAdd(false)
      setForm(emptyForm)
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

  if (!char) return null

  const items: Item[] = char.items ?? []
  const totalWeight = items.reduce((sum, i) => sum + i.weight * i.quantity, 0)

  return (
    <Layout title={t('character.inventory.title')} backTo={`/char/${charId}`}>
      <div className="flex gap-2 items-center">
        <button
          onClick={() => setShowAdd(true)}
          className="flex-1 py-3 rounded-2xl bg-[var(--tg-theme-button-color)]
                     text-[var(--tg-theme-button-text-color)] font-semibold"
        >
          + {t('character.inventory.add')}
        </button>
        <Card className="!py-2 !px-3">
          <p className="text-xs text-[var(--tg-theme-hint-color)]">{t('character.inventory.carry', {
            enc: totalWeight.toFixed(1),
            cap: char.carry_capacity,
          })}</p>
        </Card>
      </div>

      {items.length === 0 && (
        <Card>
          <p className="text-center text-[var(--tg-theme-hint-color)]">{t('common.none')}</p>
        </Card>
      )}

      <div className="space-y-2">
        {items.map((item) => (
          <Card key={item.id}>
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium truncate">{item.name}</span>
                  {item.is_equipped && (
                    <span className="text-xs px-1.5 py-0.5 rounded-full bg-green-500/20 text-green-400 shrink-0">
                      {t('character.inventory.equipped')}
                    </span>
                  )}
                </div>
                <p className="text-xs text-[var(--tg-theme-hint-color)] mt-0.5">
                  {t(`character.inventory.types.${item.item_type}`, { defaultValue: item.item_type })}
                  {item.weight > 0 && ` · ${item.weight}lb`}
                </p>
                {item.description && (
                  <p className="text-xs text-[var(--tg-theme-hint-color)] mt-1 line-clamp-2">{item.description}</p>
                )}
              </div>
              <div className="flex flex-col items-end gap-1 shrink-0">
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => updateQty.mutate({ itemId: item.id, quantity: item.quantity - 1 })}
                    className="w-6 h-6 rounded-lg bg-white/10 text-sm font-bold active:opacity-70"
                  >−</button>
                  <span className="w-6 text-center text-sm font-bold">{item.quantity}</span>
                  <button
                    onClick={() => updateQty.mutate({ itemId: item.id, quantity: item.quantity + 1 })}
                    className="w-6 h-6 rounded-lg bg-white/10 text-sm font-bold active:opacity-70"
                  >+</button>
                </div>
                <div className="flex gap-1">
                  <button
                    onClick={() => toggleEquip.mutate({ itemId: item.id, equipped: !item.is_equipped })}
                    className="text-xs text-[var(--tg-theme-link-color)]"
                  >
                    {item.is_equipped ? '↩' : '⚔'}
                  </button>
                  <button
                    onClick={() => setDeleteTarget(item.id)}
                    className="text-xs text-red-400"
                  >
                    {t('common.delete')}
                  </button>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Add item sheet */}
      {showAdd && (
        <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4">
          <Card className="w-full space-y-3">
            <h3 className="font-semibold">{t('character.inventory.add')}</h3>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder={t('character.inventory.item_name')}
              className="w-full bg-white/10 rounded-xl px-3 py-2 outline-none
                         focus:ring-2 focus:ring-[var(--tg-theme-button-color)]"
            />
            <select
              value={form.item_type}
              onChange={(e) => setForm((f) => ({ ...f, item_type: e.target.value }))}
              className="w-full bg-[var(--tg-theme-secondary-bg-color)] rounded-xl px-3 py-2 outline-none"
            >
              {ITEM_TYPES.map((type) => (
                <option key={type} value={type}>
                  {t(`character.inventory.types.${type}`)}
                </option>
              ))}
            </select>
            <div className="flex gap-2">
              <div className="flex-1">
                <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.inventory.quantity')}</p>
                <input
                  type="number" min="1" value={form.quantity}
                  onChange={(e) => setForm((f) => ({ ...f, quantity: e.target.value }))}
                  className="w-full bg-white/10 rounded-xl px-3 py-2 text-center outline-none"
                />
              </div>
              <div className="flex-1">
                <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.inventory.weight')} (lb)</p>
                <input
                  type="number" min="0" step="0.1" value={form.weight}
                  onChange={(e) => setForm((f) => ({ ...f, weight: e.target.value }))}
                  className="w-full bg-white/10 rounded-xl px-3 py-2 text-center outline-none"
                />
              </div>
            </div>
            <textarea
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder={t('character.inventory.description')}
              rows={3}
              className="w-full bg-white/10 rounded-xl px-3 py-2 outline-none resize-none"
            />
            <div className="flex gap-2">
              <button
                onClick={() => addMutation.mutate()}
                disabled={!form.name.trim() || addMutation.isPending}
                className="flex-1 py-2 rounded-xl bg-[var(--tg-theme-button-color)]
                           text-[var(--tg-theme-button-text-color)] font-semibold disabled:opacity-40"
              >
                {addMutation.isPending ? '...' : t('common.add')}
              </button>
              <button onClick={() => setShowAdd(false)} className="flex-1 py-2 rounded-xl bg-white/10">
                {t('common.cancel')}
              </button>
            </div>
          </Card>
        </div>
      )}

      {deleteTarget !== null && (
        <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4">
          <Card className="w-full">
            <p className="text-sm text-center mb-3">
              {t('character.select.delete_confirm', {
                name: items.find((i) => i.id === deleteTarget)?.name ?? '',
              })}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => deleteMutation.mutate(deleteTarget)}
                className="flex-1 py-2 rounded-xl bg-red-500/80 text-white font-medium"
              >
                {t('common.delete')}
              </button>
              <button onClick={() => setDeleteTarget(null)} className="flex-1 py-2 rounded-xl bg-white/10">
                {t('common.cancel')}
              </button>
            </div>
          </Card>
        </div>
      )}
    </Layout>
  )
}

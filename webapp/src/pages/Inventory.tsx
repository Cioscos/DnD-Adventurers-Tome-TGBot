import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import { haptic } from '@/auth/telegram'
import type { Item } from '@/types'

// Item types available for creation (matching old bot)
const ITEM_TYPES = ['generic', 'weapon', 'armor', 'shield', 'consumable', 'tool'] as const
type ItemType = typeof ITEM_TYPES[number]

const DAMAGE_TYPES = [
  'dmg_slashing', 'dmg_piercing', 'dmg_bludgeoning',
  'dmg_fire', 'dmg_cold', 'dmg_lightning', 'dmg_acid', 'dmg_poison',
  'dmg_necrotic', 'dmg_radiant', 'dmg_force', 'dmg_psychic', 'dmg_thunder', 'dmg_other',
] as const

const WEAPON_PROPERTIES = [
  'prop_finesse', 'prop_versatile', 'prop_heavy', 'prop_light',
  'prop_thrown', 'prop_two_handed', 'prop_ammunition', 'prop_loading',
  'prop_reach', 'prop_special',
] as const

const ARMOR_TYPES = ['light', 'medium', 'heavy'] as const
const WEAPON_TYPES = ['melee', 'ranged'] as const

const DAMAGE_DICE_RE = /^\d+d\d+([+-]\d+)?$/

const TYPE_ICON: Record<string, string> = {
  weapon: '⚔️',
  armor: '🛡️',
  shield: '🛡️',
  consumable: '🧪',
  tool: '🔧',
  generic: '📦',
  potion: '🧪',
  scroll: '📜',
  gear: '🎒',
  other: '📦',
}

type AddForm = {
  name: string
  item_type: ItemType
  quantity: string
  weight: string
  description: string
  // weapon
  damage_dice: string
  damage_type: string
  weapon_type: string
  properties: string[]
  // armor
  armor_type: string
  ac_value: string
  stealth_disadvantage: boolean
  strength_req: string
  // shield
  ac_bonus: string
  // consumable
  effect: string
  // tool
  tool_type: string
}

const emptyForm: AddForm = {
  name: '',
  item_type: 'generic',
  quantity: '1',
  weight: '0',
  description: '',
  damage_dice: '1d6',
  damage_type: 'dmg_slashing',
  weapon_type: 'melee',
  properties: [],
  armor_type: 'light',
  ac_value: '11',
  stealth_disadvantage: false,
  strength_req: '0',
  ac_bonus: '2',
  effect: '',
  tool_type: '',
}

function buildMetadata(form: AddForm): Record<string, unknown> | undefined {
  switch (form.item_type) {
    case 'weapon':
      return {
        damage_dice: form.damage_dice,
        damage_type: form.damage_type,
        weapon_type: form.weapon_type,
        properties: form.properties,
      }
    case 'armor':
      return {
        armor_type: form.armor_type,
        ac_value: Number(form.ac_value) || 10,
        stealth_disadvantage: form.stealth_disadvantage,
        strength_req: Number(form.strength_req) || 0,
      }
    case 'shield':
      return { ac_bonus: Number(form.ac_bonus) || 2 }
    case 'consumable':
      return form.effect ? { effect: form.effect } : undefined
    case 'tool':
      return form.tool_type ? { tool_type: form.tool_type } : undefined
    default:
      return undefined
  }
}

function isWeaponFormValid(form: AddForm): boolean {
  return DAMAGE_DICE_RE.test(form.damage_dice.trim())
}

function isFormValid(form: AddForm): boolean {
  if (!form.name.trim()) return false
  if (form.item_type === 'weapon' && !isWeaponFormValid(form)) return false
  if (form.item_type === 'armor' && (Number(form.ac_value) < 1 || isNaN(Number(form.ac_value)))) return false
  return true
}

function ItemMetaBadge({ item, t }: { item: Item; t: (k: string, opts?: Record<string, unknown>) => string }) {
  const meta = item.item_metadata as Record<string, unknown> | undefined
  if (!meta) return null

  if (item.item_type === 'weapon') {
    const dmgType = t(`character.inventory.damage_types.${meta.damage_type}`, { defaultValue: String(meta.damage_type ?? '') })
    const wpnType = t(`character.inventory.weapon_type.${meta.weapon_type}`, { defaultValue: String(meta.weapon_type ?? '') })
    const props = Array.isArray(meta.properties) && meta.properties.length > 0
      ? meta.properties.map((p: unknown) => t(`character.inventory.weapon_properties.${p}`, { defaultValue: String(p) })).join(', ')
      : null
    return (
      <div className="text-xs text-[var(--tg-theme-hint-color)] mt-0.5 space-y-0.5">
        <p>{meta.damage_dice as string} · {dmgType} · {wpnType}</p>
        {props && <p>{props}</p>}
      </div>
    )
  }

  if (item.item_type === 'armor') {
    const armorType = t(`character.inventory.armor_type.${meta.armor_type}`, { defaultValue: String(meta.armor_type ?? '') })
    return (
      <div className="text-xs text-[var(--tg-theme-hint-color)] mt-0.5 space-y-0.5">
        <p>{armorType} · CA {String(meta.ac_value ?? '?')}{meta.stealth_disadvantage ? ' · ⚠️ Furtività' : ''}{Number(meta.strength_req) > 0 ? ` · FOR ${meta.strength_req}+` : ''}</p>
      </div>
    )
  }

  if (item.item_type === 'shield') {
    return (
      <p className="text-xs text-[var(--tg-theme-hint-color)] mt-0.5">+{String(meta.ac_bonus ?? 2)} CA</p>
    )
  }

  if (item.item_type === 'consumable' && meta.effect) {
    return <p className="text-xs text-[var(--tg-theme-hint-color)] mt-0.5 line-clamp-2">{String(meta.effect)}</p>
  }

  if (item.item_type === 'tool' && meta.tool_type) {
    return <p className="text-xs text-[var(--tg-theme-hint-color)] mt-0.5">{String(meta.tool_type)}</p>
  }

  return null
}

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
        item_metadata: buildMetadata(form),
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

  const toggleProperty = (prop: string) => {
    setForm((f) => ({
      ...f,
      properties: f.properties.includes(prop)
        ? f.properties.filter((p) => p !== prop)
        : [...f.properties, prop],
    }))
  }

  if (!char) return null

  const items: Item[] = char.items ?? []
  const totalWeight = items.reduce((sum, i) => sum + i.weight * i.quantity, 0)

  const inputCls = 'w-full bg-white/10 rounded-xl px-3 py-2 outline-none focus:ring-2 focus:ring-[var(--tg-theme-button-color)]'
  const selectCls = 'w-full bg-[var(--tg-theme-secondary-bg-color)] rounded-xl px-3 py-2 outline-none'
  const labelCls = 'text-xs text-[var(--tg-theme-hint-color)] mb-1'

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
        {items.map((item) => {
          const icon = TYPE_ICON[item.item_type] ?? '📦'
          const meta = item.item_metadata as Record<string, unknown> | undefined
          return (
            <Card key={item.id}>
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium">{icon} {item.name}</span>
                    {item.is_equipped && (
                      <span className="text-xs px-1.5 py-0.5 rounded-full bg-green-500/20 text-green-400 shrink-0">
                        {t('character.inventory.equipped')}
                      </span>
                    )}
                    {item.is_equipped && item.item_type === 'armor' && meta?.ac_value != null && (
                      <span className="text-xs px-1.5 py-0.5 rounded-full bg-blue-500/20 text-blue-400 shrink-0">
                        CA {String(meta.ac_value)}
                      </span>
                    )}
                    {item.is_equipped && item.item_type === 'shield' && meta?.ac_bonus != null && (
                      <span className="text-xs px-1.5 py-0.5 rounded-full bg-blue-500/20 text-blue-400 shrink-0">
                        +{String(meta.ac_bonus)} CA
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-[var(--tg-theme-hint-color)] mt-0.5">
                    {t(`character.inventory.types.${item.item_type}`, { defaultValue: item.item_type })}
                    {item.weight > 0 && ` · ${item.weight}lb`}
                  </p>
                  <ItemMetaBadge item={item} t={t} />
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
          )
        })}
      </div>

      {/* Add item sheet */}
      {showAdd && (
        <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4 overflow-y-auto">
          <Card className="w-full space-y-3 max-h-[90vh] overflow-y-auto">
            <h3 className="font-semibold">{t('character.inventory.add')}</h3>

            {/* Name */}
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder={t('character.inventory.item_name')}
              className={inputCls}
            />

            {/* Type */}
            <div>
              <p className={labelCls}>{t('character.inventory.item_type')}</p>
              <select
                value={form.item_type}
                onChange={(e) => setForm((f) => ({ ...f, item_type: e.target.value as ItemType }))}
                className={selectCls}
              >
                {ITEM_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {t(`character.inventory.types.${type}`)}
                  </option>
                ))}
              </select>
            </div>

            {/* === WEAPON fields === */}
            {form.item_type === 'weapon' && (
              <>
                <div>
                  <p className={labelCls}>{t('character.inventory.damage_dice_label')}</p>
                  <input
                    type="text"
                    value={form.damage_dice}
                    onChange={(e) => setForm((f) => ({ ...f, damage_dice: e.target.value }))}
                    placeholder="1d8"
                    className={`${inputCls} ${!DAMAGE_DICE_RE.test(form.damage_dice.trim()) && form.damage_dice ? 'ring-2 ring-red-500' : ''}`}
                  />
                </div>
                <div>
                  <p className={labelCls}>{t('character.inventory.damage_type_label')}</p>
                  <select
                    value={form.damage_type}
                    onChange={(e) => setForm((f) => ({ ...f, damage_type: e.target.value }))}
                    className={selectCls}
                  >
                    {DAMAGE_TYPES.map((dt) => (
                      <option key={dt} value={dt}>
                        {t(`character.inventory.damage_types.${dt}`)}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <p className={labelCls}>{t('character.inventory.weapon_type_label')}</p>
                  <div className="flex gap-2">
                    {WEAPON_TYPES.map((wt) => (
                      <button
                        key={wt}
                        type="button"
                        onClick={() => setForm((f) => ({ ...f, weapon_type: wt }))}
                        className={`flex-1 py-2 rounded-xl text-sm font-medium transition-colors ${
                          form.weapon_type === wt
                            ? 'bg-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-text-color)]'
                            : 'bg-white/10'
                        }`}
                      >
                        {t(`character.inventory.weapon_type.${wt}`)}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className={labelCls}>{t('character.inventory.properties_label')}</p>
                  <div className="flex flex-wrap gap-2">
                    {WEAPON_PROPERTIES.map((prop) => (
                      <button
                        key={prop}
                        type="button"
                        onClick={() => toggleProperty(prop)}
                        className={`px-2 py-1 rounded-lg text-xs font-medium transition-colors ${
                          form.properties.includes(prop)
                            ? 'bg-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-text-color)]'
                            : 'bg-white/10'
                        }`}
                      >
                        {form.properties.includes(prop) ? '✓ ' : ''}{t(`character.inventory.weapon_properties.${prop}`)}
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}

            {/* === ARMOR fields === */}
            {form.item_type === 'armor' && (
              <>
                <div>
                  <p className={labelCls}>{t('character.inventory.armor_type_label')}</p>
                  <div className="flex gap-2">
                    {ARMOR_TYPES.map((at) => (
                      <button
                        key={at}
                        type="button"
                        onClick={() => setForm((f) => ({ ...f, armor_type: at }))}
                        className={`flex-1 py-2 rounded-xl text-sm font-medium transition-colors ${
                          form.armor_type === at
                            ? 'bg-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-text-color)]'
                            : 'bg-white/10'
                        }`}
                      >
                        {t(`character.inventory.armor_type.${at}`)}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="flex gap-2">
                  <div className="flex-1">
                    <p className={labelCls}>{t('character.inventory.ac_value_label')}</p>
                    <input
                      type="number" min="1"
                      value={form.ac_value}
                      onChange={(e) => setForm((f) => ({ ...f, ac_value: e.target.value }))}
                      className={`${inputCls} text-center`}
                    />
                  </div>
                  <div className="flex-1">
                    <p className={labelCls}>{t('character.inventory.strength_req_label')}</p>
                    <input
                      type="number" min="0"
                      value={form.strength_req}
                      onChange={(e) => setForm((f) => ({ ...f, strength_req: e.target.value }))}
                      className={`${inputCls} text-center`}
                    />
                  </div>
                </div>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.stealth_disadvantage}
                    onChange={(e) => setForm((f) => ({ ...f, stealth_disadvantage: e.target.checked }))}
                    className="w-4 h-4 rounded"
                  />
                  <span className="text-sm">{t('character.inventory.stealth_disadvantage_label')}</span>
                </label>
              </>
            )}

            {/* === SHIELD fields === */}
            {form.item_type === 'shield' && (
              <div>
                <p className={labelCls}>{t('character.inventory.ac_bonus_label')}</p>
                <input
                  type="number" min="0"
                  value={form.ac_bonus}
                  onChange={(e) => setForm((f) => ({ ...f, ac_bonus: e.target.value }))}
                  className={`${inputCls} text-center`}
                />
              </div>
            )}

            {/* === CONSUMABLE fields === */}
            {form.item_type === 'consumable' && (
              <div>
                <p className={labelCls}>{t('character.inventory.effect_label')}</p>
                <textarea
                  value={form.effect}
                  onChange={(e) => setForm((f) => ({ ...f, effect: e.target.value }))}
                  rows={2}
                  className={`${inputCls} resize-none`}
                />
              </div>
            )}

            {/* === TOOL fields === */}
            {form.item_type === 'tool' && (
              <div>
                <p className={labelCls}>{t('character.inventory.tool_type_label')}</p>
                <input
                  type="text"
                  value={form.tool_type}
                  onChange={(e) => setForm((f) => ({ ...f, tool_type: e.target.value }))}
                  className={inputCls}
                />
              </div>
            )}

            {/* Quantity & Weight */}
            <div className="flex gap-2">
              <div className="flex-1">
                <p className={labelCls}>{t('character.inventory.quantity')}</p>
                <input
                  type="number" min="1" value={form.quantity}
                  onChange={(e) => setForm((f) => ({ ...f, quantity: e.target.value }))}
                  className={`${inputCls} text-center`}
                />
              </div>
              <div className="flex-1">
                <p className={labelCls}>{t('character.inventory.weight')} (lb)</p>
                <input
                  type="number" min="0" step="0.1" value={form.weight}
                  onChange={(e) => setForm((f) => ({ ...f, weight: e.target.value }))}
                  className={`${inputCls} text-center`}
                />
              </div>
            </div>

            {/* Description */}
            <textarea
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder={t('character.inventory.description')}
              rows={2}
              className={`${inputCls} resize-none`}
            />

            <div className="flex gap-2">
              <button
                onClick={() => addMutation.mutate()}
                disabled={!isFormValid(form) || addMutation.isPending}
                className="flex-1 py-2 rounded-xl bg-[var(--tg-theme-button-color)]
                           text-[var(--tg-theme-button-text-color)] font-semibold disabled:opacity-40"
              >
                {addMutation.isPending ? '...' : t('common.add')}
              </button>
              <button onClick={() => { setShowAdd(false); setForm(emptyForm) }} className="flex-1 py-2 rounded-xl bg-white/10">
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

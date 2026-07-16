import React from 'react'
import { useTranslation } from 'react-i18next'
import { Pencil, Trash2, ArrowLeftRight, Weight, Shield, AlertTriangle, Wrench, Share2 } from 'lucide-react'
import {
  GiCrossedSwords as Swords,
  GiArcheryTarget as Target,
  GiPotionBall as FlaskConical,
  GiBiceps as Biceps,
  GiBackpack as Backpack,
} from 'react-icons/gi'
import { TYPE_ICON, consumableEmoji, hasSingleQuantity } from './itemMetadata'
import type { Item } from '@/types'
import type { Property } from '@/lib/homebrew/types'
import PropertyBadge from '@/components/homebrew/PropertyBadge'
import { useUnitSettings, formatWeight } from '@/store/unitSettings'
import Pressable from '@/components/ui/Pressable'

/**
 * A homebrew Property resolved from an active rule, paired with the item types
 * the rule applies to (`null` = no `item_types` filter → applies to every item).
 */
export type ItemProperty = {
  property: Property
  itemTypes: string[] | null
}

/* ---------- Stat chip (matches SpellItem chip style) ---------- */

function Chip({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-1.5 bg-dnd-chip-bg rounded-lg px-2 py-1.5">
      <span className="text-dnd-gold-dim shrink-0 inline-flex">{icon}</span>
      <span className="text-xs font-medium text-dnd-text truncate">{children}</span>
    </div>
  )
}

/* ---------- Type-specific stat chips ---------- */

function ItemStatChips({ item }: { item: Item }) {
  const { t } = useTranslation()
  const system = useUnitSettings((s) => s.system)
  const meta = item.item_metadata as Record<string, unknown> | undefined
  const chips: React.ReactNode[] = []

  // Common: type
  chips.push(
    <Chip key="type" icon={<Backpack size={12} />}>
      {t(`character.inventory.types.${item.item_type}`, { defaultValue: item.item_type })}
    </Chip>
  )

  // Common: weight (only when > 0)
  if (item.weight > 0) {
    chips.push(
      <Chip key="weight" icon={<Weight size={12} />}>
        {formatWeight(item.weight, system)}
      </Chip>
    )
  }

  // Type-specific
  if (meta) {
    if (item.item_type === 'weapon') {
      const dmgType = t(`character.inventory.damage_types.${meta.damage_type}`, { defaultValue: String(meta.damage_type ?? '') })
      const wpnType = t(`character.inventory.weapon_type.${meta.weapon_type}`, { defaultValue: String(meta.weapon_type ?? '') })
      chips.push(
        <Chip key="dmg" icon={<Swords size={12} />}>
          {String(meta.damage_dice ?? '')} {dmgType}
        </Chip>
      )
      chips.push(
        <Chip key="wpn" icon={<Target size={12} />}>
          {wpnType}
        </Chip>
      )
    } else if (item.item_type === 'armor') {
      const armorType = t(`character.inventory.armor_type.${meta.armor_type}`, { defaultValue: String(meta.armor_type ?? '') })
      chips.push(
        <Chip key="armor" icon={<Shield size={12} />}>
          {armorType} · CA {String(meta.ac_value ?? '?')}
        </Chip>
      )
      if (meta.stealth_disadvantage) {
        chips.push(
          <Chip key="stealth" icon={<AlertTriangle size={12} />}>
            {t('character.inventory.stealth_disadvantage', { defaultValue: 'Furtività svantaggio' })}
          </Chip>
        )
      }
      if (Number(meta.strength_req) > 0) {
        chips.push(
          <Chip key="strreq" icon={<Biceps size={12} />}>
            FOR {String(meta.strength_req)}+
          </Chip>
        )
      }
    } else if (item.item_type === 'shield') {
      chips.push(
        <Chip key="shield" icon={<Shield size={12} />}>
          +{String(meta.ac_bonus ?? 2)} CA
        </Chip>
      )
    } else if (item.item_type === 'tool' && meta.tool_type) {
      chips.push(
        <Chip key="tool" icon={<Wrench size={12} />}>
          {String(meta.tool_type)}
        </Chip>
      )
    }
  }

  return chips.length > 0 ? (
    <div className="grid grid-cols-2 gap-1.5">{chips}</div>
  ) : null
}

/* ---------- Weapon properties (separate row) ---------- */

function WeaponPropertyTags({ item }: { item: Item }) {
  const { t } = useTranslation()
  const meta = item.item_metadata as Record<string, unknown> | undefined
  if (item.item_type !== 'weapon' || !meta) return null
  const props = Array.isArray(meta.properties) ? meta.properties : []
  if (props.length === 0) return null

  return (
    <div className="flex flex-wrap gap-1">
      {props.map((p, i) => (
        <span
          key={i}
          className="text-[10px] font-medium px-1.5 py-0.5 rounded-md bg-dnd-chip-bg text-dnd-text-muted select-none pointer-events-none"
        >
          {t(`character.inventory.weapon_properties.${p}`, { defaultValue: String(p) })}
        </span>
      ))}
    </div>
  )
}

/* ---------- Consumable / potion / scroll effect (paragraph callout) ---------- */

function ItemEffectCallout({ item }: { item: Item }) {
  const { t } = useTranslation()
  const meta = item.item_metadata as Record<string, unknown> | undefined
  if (!meta?.effect) return null
  if (!['consumable', 'potion', 'scroll'].includes(item.item_type)) return null
  return (
    <div className="bg-dnd-highlight/10 border border-dnd-highlight/20 rounded-lg px-2 py-1.5">
      <span className="text-[10px] uppercase tracking-wide text-dnd-highlight-muted block mb-0.5 inline-flex items-center gap-1">
        <FlaskConical size={11} /> {t('character.inventory.effect_label')}
      </span>
      <p className="text-xs text-dnd-highlight-muted leading-relaxed whitespace-pre-wrap">
        {String(meta.effect)}
      </p>
    </div>
  )
}

/* ---------- Homebrew property chips ---------- */

function HomebrewPropertyChips({
  item,
  propertyByKey,
  locale,
  onSetProperty,
  pending,
}: {
  item: Item
  propertyByKey: Map<string, ItemProperty>
  locale: 'it' | 'en'
  onSetProperty: (itemId: number, key: string, value: unknown) => void
  pending: boolean
}) {
  const meta = item.item_metadata as Record<string, unknown> | undefined

  // Iterate over EVERY active property whose rule applies to this item type —
  // not just keys already present in item_metadata. Properties without a stored
  // metadata value fall back to their `default`, so e.g. `enchanted` (default
  // false) and `quality` (default "ordinaria") are editable on a pristine item.
  const entries: Array<[string, unknown, Property]> = []
  for (const { property, itemTypes } of propertyByKey.values()) {
    // Respect the rule's subject `item_types` filter (null = all items).
    if (itemTypes && !itemTypes.includes(item.item_type)) continue
    const stored = meta?.[`hb_${property.key}`]
    const value = stored !== undefined ? stored : property.default
    entries.push([property.key, value, property])
  }
  if (entries.length === 0) return null

  return (
    <div className="grid grid-cols-2 gap-1.5">
      {entries.map(([key, value, property]) => (
        // Number badges (label + value + two 44px steppers) can't stay legible in
        // a ~167px half-column at 375px, so they span the full row (#35).
        <div key={key} className={property.type === 'number' ? 'col-span-2' : undefined}>
          <PropertyBadge
            propertyKey={key}
            value={value}
            property={property}
            locale={locale}
            onSetProperty={(k, v) => onSetProperty(item.id, k, v)}
            disabled={pending}
          />
        </div>
      ))}
    </div>
  )
}

/* ---------- Main component ---------- */

interface InventoryItemProps {
  item: Item
  isExpanded: boolean
  onToggle: () => void
  onEquipToggle: () => void
  onQuantityChange: (delta: number) => void
  onAttack: () => void
  onUse: () => void
  onEdit: () => void
  onDelete: () => void
  /** Presente solo quando il client supporta shareMessage (Bot API 8.0+). */
  onShare?: () => void
  equipPending: boolean
  attackPending: boolean
  usePending: boolean
  /** Mutazione condivisa di quantità (P4, già scoped sull'item dal padre). */
  quantityPending: boolean
  /** Mutazione condivisa di condivisione (P4, già scoped sull'item dal padre). */
  sharePending: boolean
  propertyByKey: Map<string, ItemProperty>
  locale: 'it' | 'en'
  onSetProperty: (itemId: number, key: string, value: unknown) => void
  setPropertyPending: boolean
}

function InventoryItemInner({
  item,
  isExpanded,
  onToggle,
  onEquipToggle,
  onQuantityChange,
  onAttack,
  onUse,
  onEdit,
  onDelete,
  onShare,
  equipPending,
  attackPending,
  usePending,
  quantityPending,
  sharePending,
  propertyByKey,
  locale,
  onSetProperty,
  setPropertyPending,
}: InventoryItemProps) {
  const { t } = useTranslation()
  const system = useUnitSettings((s) => s.system)
  const meta = item.item_metadata as Record<string, unknown> | undefined
  const icon = item.item_type === 'consumable'
    ? consumableEmoji(meta?.subtype as string | undefined)
    : (TYPE_ICON[item.item_type] ?? '📦')
  const canEquip = ['armor', 'shield', 'weapon', 'accessory'].includes(item.item_type)
  const effects = Array.isArray(meta?.effects) ? (meta.effects as unknown[]) : []
  const canUse = item.item_type === 'consumable' && effects.length > 0

  return (
    <div
      className={`rounded-2xl bg-dnd-surface overflow-hidden border
        ${item.is_equipped ? 'border-dnd-emerald/60' : 'border-transparent'}`}
    >
      {/* Header row — tap to expand */}
      <Pressable
        className="w-full flex items-center gap-2 px-4 py-3 text-left active:opacity-70"
        onClick={onToggle}
      >
        <span className="text-lg shrink-0">{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm text-dnd-text">{item.name}</span>
            {item.is_equipped && (
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-md bg-dnd-emerald/20 text-dnd-emerald-bright border border-dnd-emerald/30">
                {t('character.inventory.equipped')}
              </span>
            )}
            {item.is_equipped && item.item_type === 'armor' && meta?.ac_value != null && (
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-md bg-dnd-info/20 text-dnd-info-text border border-dnd-info/30">
                CA {String(meta.ac_value)}
              </span>
            )}
            {item.is_equipped && item.item_type === 'shield' && meta?.ac_bonus != null && (
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-md bg-dnd-info/20 text-dnd-info-text border border-dnd-info/30">
                +{String(meta.ac_bonus)} CA
              </span>
            )}
          </div>
          <p className="text-xs text-dnd-text-muted mt-0.5">
            {t(`character.inventory.types.${item.item_type}`, { defaultValue: item.item_type })}
            {item.weight > 0 && ` · ${formatWeight(item.weight, system)}`}
            {!hasSingleQuantity(item.item_type) && ` · ×${item.quantity}`}
          </p>
        </div>
        <span className="text-dnd-text-muted text-xs shrink-0 ml-1">
          {isExpanded ? '˄' : '˅'}
        </span>
      </Pressable>

      {/* Expanded detail panel */}
      {isExpanded && (
        <div className="spell-detail-enter px-3 pt-3 pb-3 space-y-3 border-t border-dnd-gold-dim/10">
          {/* Description */}
          {item.description && (
            <p className="text-sm text-dnd-text whitespace-pre-wrap leading-relaxed italic">
              {item.description}
            </p>
          )}

          {/* Stat chips */}
          <ItemStatChips item={item} />

          {/* Homebrew property chips — editable, resolved against active rules */}
          <HomebrewPropertyChips
            item={item}
            propertyByKey={propertyByKey}
            locale={locale}
            onSetProperty={onSetProperty}
            pending={setPropertyPending}
          />

          {/* Weapon properties tags */}
          <WeaponPropertyTags item={item} />

          {/* Effect callout (consumable / potion / scroll) */}
          <ItemEffectCallout item={item} />

          {/* Quantity stepper — hidden for single-equip items (weapon, armor, shield) */}
          {!hasSingleQuantity(item.item_type) && (
            <div className="flex items-center gap-2 bg-dnd-chip-bg rounded-lg px-2 py-1.5">
              <span className="text-xs text-dnd-text-muted flex-1 font-medium">
                {t('character.inventory.quantity')}
              </span>
              <Pressable
                onClick={() => onQuantityChange(-1)}
                pending={quantityPending}
                spinnerSize={12}
                className="w-11 h-11 rounded-md bg-dnd-surface-raised border border-dnd-border text-dnd-gold font-bold active:opacity-60"
                aria-label={t('character.inventory.quantity_decrease')}
              >&minus;</Pressable>
              <span className="w-6 text-center font-mono font-bold text-dnd-gold-bright">{item.quantity}</span>
              <Pressable
                onClick={() => onQuantityChange(1)}
                pending={quantityPending}
                spinnerSize={12}
                className="w-11 h-11 rounded-md bg-dnd-surface-raised border border-dnd-border text-dnd-gold font-bold active:opacity-60"
                aria-label={t('character.inventory.quantity_increase')}
              >+</Pressable>
            </div>
          )}

          {/* Action buttons — same pattern as SpellItem */}
          <div className="flex gap-2 flex-wrap border-t border-dnd-gold-dim/10 pt-2">
            {canEquip && (
              <Pressable
                onClick={onEquipToggle}
                pending={equipPending}
                spinnerSize={12}
                className={`flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg border active:opacity-60 disabled:opacity-30
                  ${item.is_equipped
                    ? 'bg-dnd-amber/15 text-dnd-amber border-dnd-amber/30'
                    : 'bg-dnd-emerald/20 text-dnd-emerald-bright border-dnd-emerald/30'
                  }`}
              >
                {item.is_equipped ? <ArrowLeftRight size={12} /> : <Swords size={12} />}
                {item.is_equipped ? t('character.inventory.unequip') : t('character.inventory.equip')}
              </Pressable>
            )}
            {item.item_type === 'weapon' && (
              <Pressable
                onClick={onAttack}
                pending={attackPending}
                spinnerSize={12}
                className="flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg
                           bg-dnd-crimson/20 text-dnd-crimson-bright border border-dnd-crimson/30
                           active:opacity-60 disabled:opacity-30"
              >
                <Target size={12} />
                {t('character.inventory.attack')}
              </Pressable>
            )}
            {canUse && (
              <Pressable
                onClick={onUse}
                disabled={usePending || item.quantity <= 0}
                className="flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg
                           bg-dnd-emerald/20 text-dnd-emerald-bright border border-dnd-emerald/30
                           active:opacity-60 disabled:opacity-30"
              >
                <FlaskConical size={12} />
                {t('character.inventory.use')}
              </Pressable>
            )}
            {onShare && (
              <Pressable
                onClick={onShare}
                pending={sharePending}
                spinnerSize={12}
                className="flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg
                           bg-dnd-surface text-dnd-gold border border-dnd-gold-dim/40
                           active:opacity-60"
              >
                <Share2 size={12} />
                {t('share.action')}
              </Pressable>
            )}
            <Pressable
              onClick={onEdit}
              className="flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg
                         bg-dnd-info/20 text-dnd-info-text border border-dnd-info/30
                         active:opacity-60"
            >
              <Pencil size={12} />
              {t('common.edit')}
            </Pressable>
            <Pressable
              onClick={onDelete}
              className="flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg
                         bg-dnd-crimson/15 text-dnd-crimson-bright border border-dnd-crimson/30
                         active:opacity-60"
            >
              <Trash2 size={12} />
              {t('common.delete')}
            </Pressable>
          </div>
        </div>
      )}
    </div>
  )
}

const InventoryItem = React.memo(InventoryItemInner)
export default InventoryItem

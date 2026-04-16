import React from 'react'
import { useTranslation } from 'react-i18next'
import DndButton from '@/components/DndButton'
import { TYPE_ICON } from './itemMetadata'
import type { Item } from '@/types'

/* ---------- Metadata badge sub-component ---------- */

function ItemMetaBadge({ item }: { item: Item }) {
  const { t } = useTranslation()
  const meta = item.item_metadata as Record<string, unknown> | undefined
  if (!meta) return null

  if (item.item_type === 'weapon') {
    const dmgType = t(`character.inventory.damage_types.${meta.damage_type}`, { defaultValue: String(meta.damage_type ?? '') })
    const wpnType = t(`character.inventory.weapon_type.${meta.weapon_type}`, { defaultValue: String(meta.weapon_type ?? '') })
    const props = Array.isArray(meta.properties) && meta.properties.length > 0
      ? meta.properties.map((p: unknown) => t(`character.inventory.weapon_properties.${p}`, { defaultValue: String(p) })).join(', ')
      : null
    return (
      <div className="text-xs text-dnd-text-secondary mt-0.5 space-y-0.5">
        <p>{meta.damage_dice as string} &middot; {dmgType} &middot; {wpnType}</p>
        {props && <p>{props}</p>}
      </div>
    )
  }

  if (item.item_type === 'armor') {
    const armorType = t(`character.inventory.armor_type.${meta.armor_type}`, { defaultValue: String(meta.armor_type ?? '') })
    return (
      <div className="text-xs text-dnd-text-secondary mt-0.5 space-y-0.5">
        <p>{armorType} &middot; CA {String(meta.ac_value ?? '?')}{meta.stealth_disadvantage ? ' \u00B7 \u26A0\uFE0F Furtivit\u00E0' : ''}{Number(meta.strength_req) > 0 ? ` \u00B7 FOR ${meta.strength_req}+` : ''}</p>
      </div>
    )
  }

  if (item.item_type === 'shield') {
    return (
      <p className="text-xs text-dnd-text-secondary mt-0.5">+{String(meta.ac_bonus ?? 2)} CA</p>
    )
  }

  if (item.item_type === 'consumable' && meta.effect) {
    return <p className="text-xs text-dnd-text-secondary mt-0.5 line-clamp-2">{String(meta.effect)}</p>
  }

  if (item.item_type === 'tool' && meta.tool_type) {
    return <p className="text-xs text-dnd-text-secondary mt-0.5">{String(meta.tool_type)}</p>
  }

  return null
}

/* ---------- Main component ---------- */

interface InventoryItemProps {
  item: Item
  isExpanded: boolean
  onToggle: () => void
  onEquipToggle: () => void
  onQuantityChange: (delta: number) => void
  onAttack: () => void
  onEdit: () => void
  onDelete: () => void
  equipPending: boolean
  attackPending: boolean
}

function InventoryItemInner({
  item,
  isExpanded,
  onToggle,
  onEquipToggle,
  onQuantityChange,
  onAttack,
  onEdit,
  onDelete,
  equipPending,
  attackPending,
}: InventoryItemProps) {
  const { t } = useTranslation()
  const icon = TYPE_ICON[item.item_type] ?? '\uD83D\uDCE6'
  const meta = item.item_metadata as Record<string, unknown> | undefined
  const canEquip = ['armor', 'shield', 'weapon'].includes(item.item_type)

  return (
    <div
      className={`rounded-2xl overflow-hidden bg-dnd-surface
        ${item.is_equipped ? 'ring-1 ring-dnd-success/50' : ''}`}
    >
      {/* Header row -- tap to expand */}
      <button
        className="w-full flex items-center gap-2 px-4 py-3 text-left active:opacity-70"
        onClick={onToggle}
      >
        <span className="text-lg shrink-0">{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm">{item.name}</span>
            {item.is_equipped && (
              <span className="text-xs px-1.5 py-0.5 rounded-full bg-dnd-success/20 text-dnd-success-text shrink-0">
                {t('character.inventory.equipped')}
              </span>
            )}
            {item.is_equipped && item.item_type === 'armor' && meta?.ac_value != null && (
              <span className="text-xs px-1.5 py-0.5 rounded-full bg-dnd-info/20 text-dnd-info-text shrink-0">
                CA {String(meta.ac_value)}
              </span>
            )}
            {item.is_equipped && item.item_type === 'shield' && meta?.ac_bonus != null && (
              <span className="text-xs px-1.5 py-0.5 rounded-full bg-dnd-info/20 text-dnd-info-text shrink-0">
                +{String(meta.ac_bonus)} CA
              </span>
            )}
          </div>
          <p className="text-xs text-dnd-text-secondary mt-0.5">
            {t(`character.inventory.types.${item.item_type}`, { defaultValue: item.item_type })}
            {item.weight > 0 && ` \u00B7 ${item.weight}lb`}
            {` \u00B7 \u00D7${item.quantity}`}
          </p>
        </div>
        <span className="text-dnd-text-secondary text-xs shrink-0">
          {isExpanded ? '\u25B2' : '\u25BC'}
        </span>
      </button>

      {/* Expanded detail panel */}
      {isExpanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-dnd-gold-dim/10 pt-3">
          <ItemMetaBadge item={item} />

          {item.description && (
            <p className="text-xs text-dnd-text-secondary whitespace-pre-wrap">{item.description}</p>
          )}

          {/* Quantity controls */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-dnd-text-secondary flex-1">{t('character.inventory.quantity')}</span>
            <button
              onClick={() => onQuantityChange(-1)}
              className="w-10 h-10 rounded-xl bg-dnd-surface font-bold text-lg active:opacity-70"
            >&minus;</button>
            <span className="w-6 text-center font-bold">{item.quantity}</span>
            <button
              onClick={() => onQuantityChange(1)}
              className="w-10 h-10 rounded-xl bg-dnd-surface font-bold text-lg active:opacity-70"
            >+</button>
          </div>

          {/* Action buttons */}
          <div className="flex flex-wrap gap-2 pt-1">
            {canEquip && (
              <DndButton
                variant="secondary"
                onClick={onEquipToggle}
                disabled={equipPending}
                className={`flex-1 !text-sm ${
                  item.is_equipped
                    ? '!bg-orange-500/20 !text-orange-300 !border-orange-500/30'
                    : '!bg-dnd-success/20 !text-dnd-success-text !border-dnd-success/30'
                }`}
              >
                {item.is_equipped ? `\u21A9 ${t('character.inventory.unequip')}` : `\u2694 ${t('character.inventory.equip')}`}
              </DndButton>
            )}
            {item.item_type === 'weapon' && (
              <DndButton
                variant="secondary"
                onClick={onAttack}
                disabled={attackPending}
                className="flex-1 !text-sm !bg-orange-500/20 !text-orange-300 !border-orange-500/30"
              >
                \uD83C\uDFB2 {t('character.inventory.attack')}
              </DndButton>
            )}
            <DndButton
              variant="secondary"
              onClick={onEdit}
              className="!px-4 !text-sm !bg-dnd-info/20 !text-dnd-info-text !border-dnd-info/30"
            >
              {t('common.edit')}
            </DndButton>
            <DndButton
              variant="danger"
              onClick={onDelete}
              className="!px-4 !text-sm"
            >
              {t('common.delete')}
            </DndButton>
          </div>
        </div>
      )}
    </div>
  )
}

const InventoryItem = React.memo(InventoryItemInner)
export default InventoryItem

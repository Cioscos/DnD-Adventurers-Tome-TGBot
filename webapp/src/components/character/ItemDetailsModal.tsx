import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'
import { TYPE_ICON } from '@/pages/inventory/itemMetadata'
import { useRegisterOverlay } from '@/store/overlayStore'
import type { EquipmentSlot, Item } from '@/types'
import { useUnitSettings, formatWeight } from '@/store/unitSettings'

interface Props {
  item: Item
  slot: EquipmentSlot
  onClose: () => void
}

function MetadataField({ label, value }: { label: string; value: string | number | boolean }) {
  let displayValue: string
  if (typeof value === 'boolean') displayValue = value ? '✓' : '—'
  else displayValue = String(value)
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <span className="text-[11px] font-cinzel uppercase tracking-widest text-dnd-gold-dim shrink-0">
        {label}
      </span>
      <span className="text-sm font-body text-dnd-text text-right truncate">
        {displayValue}
      </span>
    </div>
  )
}

export default function ItemDetailsModal({ item, slot, onClose }: Props) {
  const { t } = useTranslation()
  const system = useUnitSettings((s) => s.system)
  useRegisterOverlay(true)

  const slotLabel = t(`character.equipment.slots.${slot}`, { defaultValue: slot })
  const typeLabel = t(`character.inventory.types.${item.item_type}`, { defaultValue: item.item_type })
  const typeIcon = TYPE_ICON[item.item_type] ?? TYPE_ICON.generic

  const meta = item.item_metadata ?? {}
  const properties = Array.isArray(meta.properties) ? meta.properties as string[] : []
  const abilityMods = Array.isArray(meta.ability_modifiers) ? meta.ability_modifiers as Array<{ ability: string; value: number }> : []

  return createPortal(
    <AnimatePresence>
      <m.div
        className="fixed inset-0 z-50 flex items-end justify-center backdrop-blur-sm"
        style={{ background: 'var(--dnd-overlay)' }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <m.div
          className="w-full max-w-md max-h-[85vh] flex flex-col bg-dnd-surface-raised border border-dnd-gold-dim/50 rounded-t-2xl pb-safe"
          initial={{ y: 100 }}
          animate={{ y: 0 }}
          exit={{ y: 100 }}
          transition={{ type: 'spring', stiffness: 260, damping: 28 }}
          onClick={(e) => e.stopPropagation()}
        >
          <header className="flex items-start justify-between px-4 py-3 border-b border-dnd-border">
            <div className="min-w-0 flex-1">
              <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim">
                {slotLabel}
              </p>
              <h2 className="text-base font-bold text-dnd-gold-bright leading-tight">
                <span className="mr-1.5" aria-hidden>{typeIcon}</span>
                {item.name}
              </h2>
              <p className="text-[11px] font-body italic text-dnd-text-faint mt-0.5">
                {typeLabel}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label={t('common.close', { defaultValue: 'Close' })}
              className="w-9 h-9 -mr-1 shrink-0 flex items-center justify-center rounded-full border border-dnd-gold-dim/40"
            >
              <X size={18} className="text-dnd-gold" />
            </button>
          </header>

          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            {item.description && (
              <p className="text-sm font-body text-dnd-text leading-relaxed whitespace-pre-wrap">
                {item.description}
              </p>
            )}

            <div className="divide-y divide-dnd-border/30">
              <MetadataField
                label={t('character.inventory.quantity', { defaultValue: 'Quantità' })}
                value={item.quantity}
              />
              <MetadataField
                label={t('character.inventory.weight', { defaultValue: 'Peso' })}
                value={formatWeight(item.weight, system)}
              />

              {item.item_type === 'weapon' && (
                <>
                  {meta.damage_dice !== undefined && (
                    <MetadataField
                      label={t('character.inventory.damage_dice_label', { defaultValue: 'Danni' })}
                      value={String(meta.damage_dice)}
                    />
                  )}
                  {meta.damage_type !== undefined && (
                    <MetadataField
                      label={t('character.inventory.damage_type_label', { defaultValue: 'Tipo di danno' })}
                      value={t(`character.inventory.damage_types.${meta.damage_type}`, { defaultValue: String(meta.damage_type) })}
                    />
                  )}
                  {meta.weapon_type !== undefined && (
                    <MetadataField
                      label={t('character.inventory.weapon_type_label', { defaultValue: 'Categoria' })}
                      value={t(`character.inventory.weapon_type.${meta.weapon_type}`, { defaultValue: String(meta.weapon_type) })}
                    />
                  )}
                </>
              )}

              {item.item_type === 'armor' && (
                <>
                  {meta.ac_value !== undefined && (
                    <MetadataField
                      label={t('character.inventory.ac_value_label', { defaultValue: 'Valore CA' })}
                      value={Number(meta.ac_value)}
                    />
                  )}
                  {meta.armor_type !== undefined && (
                    <MetadataField
                      label={t('character.inventory.armor_type_label', { defaultValue: 'Tipo di armatura' })}
                      value={t(`character.inventory.armor_type.${meta.armor_type}`, { defaultValue: String(meta.armor_type) })}
                    />
                  )}
                  {!!meta.stealth_disadvantage && (
                    <MetadataField
                      label={t('character.inventory.stealth_disadvantage_label', { defaultValue: 'Svantaggio Furtività' })}
                      value={true}
                    />
                  )}
                  {meta.strength_req !== undefined && Number(meta.strength_req) > 0 && (
                    <MetadataField
                      label={t('character.inventory.strength_req_label', { defaultValue: 'Requisito Forza' })}
                      value={Number(meta.strength_req)}
                    />
                  )}
                </>
              )}

              {item.item_type === 'shield' && meta.ac_bonus !== undefined && (
                <MetadataField
                  label={t('character.inventory.ac_bonus_label', { defaultValue: 'Bonus CA' })}
                  value={`+${Number(meta.ac_bonus)}`}
                />
              )}

              {(item.item_type === 'consumable' || item.item_type === 'potion' || item.item_type === 'scroll') && Boolean(meta.effect) && (
                <MetadataField
                  label={t('character.inventory.effect_label', { defaultValue: 'Effetto' })}
                  value={String(meta.effect)}
                />
              )}

              {item.item_type === 'tool' && Boolean(meta.tool_type) && (
                <MetadataField
                  label={t('character.inventory.tool_type_label', { defaultValue: 'Tipo strumento' })}
                  value={String(meta.tool_type)}
                />
              )}
            </div>

            {properties.length > 0 && (
              <div>
                <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim mb-1.5">
                  {t('character.inventory.properties_label', { defaultValue: 'Proprietà' })}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {properties.map((p) => (
                    <span
                      key={p}
                      className="px-2 py-0.5 rounded-full bg-dnd-surface border border-dnd-gold-dim/40 text-[11px] font-body text-dnd-gold-bright"
                    >
                      {t(`character.inventory.weapon_properties.${p}`, { defaultValue: p })}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {abilityMods.length > 0 && (
              <div>
                <p className="text-[10px] font-cinzel uppercase tracking-widest text-dnd-gold-dim mb-1.5">
                  {t('character.inventory.ability_modifiers_label', { defaultValue: 'Modificatori caratteristica' })}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {abilityMods.map((m, i) => (
                    <span
                      key={`${m.ability}-${i}`}
                      className="px-2 py-0.5 rounded-full bg-dnd-gold/15 border border-dnd-gold/40 text-[11px] font-body text-dnd-gold-bright"
                    >
                      {t(`character.ability.${m.ability}_short`, { defaultValue: m.ability.slice(0, 3).toUpperCase() })}
                      {' '}
                      {m.value >= 0 ? '+' : ''}{m.value}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </m.div>
      </m.div>
    </AnimatePresence>,
    document.body,
  )
}

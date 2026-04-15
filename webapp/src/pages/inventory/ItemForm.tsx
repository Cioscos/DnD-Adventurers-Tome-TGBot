import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import DndInput from '@/components/DndInput'
import DndButton from '@/components/DndButton'
import {
  ITEM_TYPES,
  DAMAGE_TYPES,
  WEAPON_PROPERTIES,
  ARMOR_TYPES,
  WEAPON_TYPES,
  DAMAGE_DICE_RE,
  emptyForm,
  isItemFormValid,
  itemToFormData,
  type ItemFormData,
  type ItemType,
} from './itemMetadata'
import type { Item } from '@/types'

interface ItemFormProps {
  initialData?: Item | null
  onSubmit: (data: ItemFormData) => void
  onCancel: () => void
  isPending: boolean
}

export default function ItemForm({ initialData, onSubmit, onCancel, isPending }: ItemFormProps) {
  const { t } = useTranslation()
  const [form, setForm] = useState<ItemFormData>(emptyForm)
  const isEditing = !!initialData

  useEffect(() => {
    if (initialData) {
      setForm(itemToFormData(initialData))
    } else {
      setForm(emptyForm)
    }
  }, [initialData])

  const toggleProperty = (prop: string) => {
    setForm((f) => ({
      ...f,
      properties: f.properties.includes(prop)
        ? f.properties.filter((p) => p !== prop)
        : [...f.properties, prop],
    }))
  }

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-end z-50 p-4"
      onFocusCapture={(e) => (e.target as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'nearest' })}
    >
      <div className="w-full rounded-2xl bg-dnd-surface-elevated p-4 space-y-3 max-h-[90vh] overflow-y-auto">
        <h3 className="font-semibold font-cinzel text-dnd-gold">
          {isEditing ? t('common.edit') : t('character.inventory.add')}
        </h3>

        {/* Name */}
        <DndInput
          label={t('character.inventory.item_name')}
          value={form.name}
          onChange={(v) => setForm((f) => ({ ...f, name: v }))}
          placeholder={t('character.inventory.item_name')}
        />

        {/* Type */}
        <div>
          <label className="block text-[11px] uppercase tracking-wider mb-1 font-medium text-dnd-gold-dim">
            {t('character.inventory.item_type')}
          </label>
          <select
            value={form.item_type}
            onChange={(e) => setForm((f) => ({ ...f, item_type: e.target.value as ItemType }))}
            className="w-full bg-dnd-surface rounded-xl px-3 py-3 min-h-[48px] outline-none text-dnd-text
                       border border-transparent focus:border-dnd-gold-dim"
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
            <DndInput
              label={t('character.inventory.damage_dice_label')}
              value={form.damage_dice}
              onChange={(v) => setForm((f) => ({ ...f, damage_dice: v }))}
              placeholder="1d8"
              error={!DAMAGE_DICE_RE.test(form.damage_dice.trim()) && form.damage_dice ? t('character.inventory.damage_dice_label') : undefined}
            />

            <div>
              <label className="block text-[11px] uppercase tracking-wider mb-1 font-medium text-dnd-gold-dim">
                {t('character.inventory.damage_type_label')}
              </label>
              <select
                value={form.damage_type}
                onChange={(e) => setForm((f) => ({ ...f, damage_type: e.target.value }))}
                className="w-full bg-dnd-surface rounded-xl px-3 py-3 min-h-[48px] outline-none text-dnd-text
                           border border-transparent focus:border-dnd-gold-dim"
              >
                {DAMAGE_TYPES.map((dt) => (
                  <option key={dt} value={dt}>
                    {t(`character.inventory.damage_types.${dt}`)}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[11px] uppercase tracking-wider mb-1 font-medium text-dnd-gold-dim">
                {t('character.inventory.weapon_type_label')}
              </label>
              <div className="flex gap-2">
                {WEAPON_TYPES.map((wt) => (
                  <DndButton
                    key={wt}
                    variant={form.weapon_type === wt ? 'primary' : 'secondary'}
                    onClick={() => setForm((f) => ({ ...f, weapon_type: wt }))}
                    className="flex-1"
                  >
                    {t(`character.inventory.weapon_type.${wt}`)}
                  </DndButton>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-[11px] uppercase tracking-wider mb-1 font-medium text-dnd-gold-dim">
                {t('character.inventory.properties_label')}
              </label>
              <div className="flex flex-wrap gap-2">
                {WEAPON_PROPERTIES.map((prop) => (
                  <button
                    key={prop}
                    type="button"
                    onClick={() => toggleProperty(prop)}
                    className={`px-2 py-1 rounded-lg text-xs font-medium transition-colors ${
                      form.properties.includes(prop)
                        ? 'bg-dnd-gold text-dnd-bg'
                        : 'bg-dnd-surface text-dnd-text'
                    }`}
                  >
                    {form.properties.includes(prop) ? '\u2713 ' : ''}{t(`character.inventory.weapon_properties.${prop}`)}
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
              <label className="block text-[11px] uppercase tracking-wider mb-1 font-medium text-dnd-gold-dim">
                {t('character.inventory.armor_type_label')}
              </label>
              <div className="flex gap-2">
                {ARMOR_TYPES.map((at) => (
                  <DndButton
                    key={at}
                    variant={form.armor_type === at ? 'primary' : 'secondary'}
                    onClick={() => setForm((f) => ({ ...f, armor_type: at }))}
                    className="flex-1"
                  >
                    {t(`character.inventory.armor_type.${at}`)}
                  </DndButton>
                ))}
              </div>
            </div>

            <div className="flex gap-2">
              <DndInput
                className="flex-1"
                label={t('character.inventory.ac_value_label')}
                type="number"
                value={form.ac_value}
                onChange={(v) => setForm((f) => ({ ...f, ac_value: v }))}
                min={1}
              />
              <DndInput
                className="flex-1"
                label={t('character.inventory.strength_req_label')}
                type="number"
                value={form.strength_req}
                onChange={(v) => setForm((f) => ({ ...f, strength_req: v }))}
                min={0}
              />
            </div>

            <label className="flex items-center gap-2 cursor-pointer text-sm text-dnd-text">
              <input
                type="checkbox"
                checked={form.stealth_disadvantage}
                onChange={(e) => setForm((f) => ({ ...f, stealth_disadvantage: e.target.checked }))}
                className="w-4 h-4 accent-dnd-gold"
              />
              {t('character.inventory.stealth_disadvantage_label')}
            </label>
          </>
        )}

        {/* === SHIELD fields === */}
        {form.item_type === 'shield' && (
          <DndInput
            label={t('character.inventory.ac_bonus_label')}
            type="number"
            value={form.ac_bonus}
            onChange={(v) => setForm((f) => ({ ...f, ac_bonus: v }))}
            min={0}
          />
        )}

        {/* === CONSUMABLE fields === */}
        {form.item_type === 'consumable' && (
          <div>
            <label className="block text-[11px] uppercase tracking-wider mb-1 font-medium text-dnd-gold-dim">
              {t('character.inventory.effect_label')}
            </label>
            <textarea
              value={form.effect}
              onChange={(e) => setForm((f) => ({ ...f, effect: e.target.value }))}
              rows={2}
              className="w-full bg-dnd-surface rounded-xl px-3 py-2 outline-none resize-none text-dnd-text
                         placeholder:text-dnd-text-secondary/50 border border-transparent
                         focus:border-dnd-gold-dim"
            />
          </div>
        )}

        {/* === TOOL fields === */}
        {form.item_type === 'tool' && (
          <DndInput
            label={t('character.inventory.tool_type_label')}
            value={form.tool_type}
            onChange={(v) => setForm((f) => ({ ...f, tool_type: v }))}
          />
        )}

        {/* Quantity & Weight */}
        <div className="flex gap-2">
          <DndInput
            className="flex-1"
            label={t('character.inventory.quantity')}
            type="number"
            value={form.quantity}
            onChange={(v) => setForm((f) => ({ ...f, quantity: v }))}
            min={1}
          />
          <DndInput
            className="flex-1"
            label={`${t('character.inventory.weight')} (lb)`}
            type="number"
            value={form.weight}
            onChange={(v) => setForm((f) => ({ ...f, weight: v }))}
            min={0}
          />
        </div>

        {/* Description */}
        <div>
          <label className="block text-[11px] uppercase tracking-wider mb-1 font-medium text-dnd-gold-dim">
            {t('character.inventory.description')}
          </label>
          <textarea
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            placeholder={t('character.inventory.description')}
            rows={2}
            className="w-full bg-dnd-surface rounded-xl px-3 py-2 outline-none resize-none text-dnd-text
                       placeholder:text-dnd-text-secondary/50 border border-transparent
                       focus:border-dnd-gold-dim"
          />
        </div>

        <div className="flex gap-2">
          <DndButton
            onClick={() => onSubmit(form)}
            disabled={!isItemFormValid(form)}
            loading={isPending}
            className="flex-1"
          >
            {isEditing ? t('common.save') : t('common.add')}
          </DndButton>
          <DndButton
            variant="secondary"
            onClick={onCancel}
            className="flex-1"
          >
            {t('common.cancel')}
          </DndButton>
        </div>
      </div>
    </div>
  )
}

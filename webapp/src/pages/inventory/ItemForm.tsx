import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import AbilityModifiersEditor from './AbilityModifiersEditor'
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

const SELECT_CLS =
  'w-full px-3 py-2.5 min-h-[48px] rounded-lg bg-dnd-surface text-dnd-text border-b-2 border-dnd-border outline-none font-body text-sm'

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
    <Sheet
      open
      onClose={onCancel}
      title={isEditing ? t('common.edit') : t('character.inventory.add')}
    >
      <div className="p-5 space-y-3">
        {/* Name */}
        <Input
          label={t('character.inventory.item_name')}
          value={form.name}
          onChange={(v) => setForm((f) => ({ ...f, name: v }))}
          placeholder={t('character.inventory.item_name')}
        />

        {/* Type */}
        <div>
          <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
            {t('character.inventory.item_type')}
          </label>
          <select
            value={form.item_type}
            onChange={(e) => setForm((f) => ({ ...f, item_type: e.target.value as ItemType }))}
            className={SELECT_CLS}
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
            <Input
              label={t('character.inventory.damage_dice_label')}
              value={form.damage_dice}
              onChange={(v) => setForm((f) => ({ ...f, damage_dice: v }))}
              placeholder="1d8"
              error={!DAMAGE_DICE_RE.test(form.damage_dice.trim()) && form.damage_dice ? t('character.inventory.damage_dice_label') : undefined}
            />

            <div>
              <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
                {t('character.inventory.damage_type_label')}
              </label>
              <select
                value={form.damage_type}
                onChange={(e) => setForm((f) => ({ ...f, damage_type: e.target.value }))}
                className={SELECT_CLS}
              >
                {DAMAGE_TYPES.map((dt) => (
                  <option key={dt} value={dt}>
                    {t(`character.inventory.damage_types.${dt}`)}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
                {t('character.inventory.weapon_type_label')}
              </label>
              <div className="flex gap-2">
                {WEAPON_TYPES.map((wt) => (
                  <Button
                    key={wt}
                    variant={form.weapon_type === wt ? 'primary' : 'secondary'}
                    size="sm"
                    fullWidth
                    onClick={() => setForm((f) => ({ ...f, weapon_type: wt }))}
                  >
                    {t(`character.inventory.weapon_type.${wt}`)}
                  </Button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
                {t('character.inventory.properties_label')}
              </label>
              <div className="flex flex-wrap gap-2">
                {WEAPON_PROPERTIES.map((prop) => {
                  const active = form.properties.includes(prop)
                  return (
                    <button
                      key={prop}
                      type="button"
                      onClick={() => toggleProperty(prop)}
                      className={`min-h-[44px] px-3 py-2 rounded-lg text-xs font-medium transition-colors
                        ${active
                          ? 'bg-dnd-gold text-dnd-ink shadow-engrave'
                          : 'bg-dnd-surface-raised text-dnd-text border border-dnd-border'}`}
                    >
                      {active ? '✓ ' : ''}{t(`character.inventory.weapon_properties.${prop}`)}
                    </button>
                  )
                })}
              </div>
            </div>
          </>
        )}

        {/* === ARMOR fields === */}
        {form.item_type === 'armor' && (
          <>
            <div>
              <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
                {t('character.inventory.armor_type_label')}
              </label>
              <div className="flex gap-2">
                {ARMOR_TYPES.map((at) => (
                  <Button
                    key={at}
                    variant={form.armor_type === at ? 'primary' : 'secondary'}
                    size="sm"
                    fullWidth
                    onClick={() => setForm((f) => ({ ...f, armor_type: at }))}
                  >
                    {t(`character.inventory.armor_type.${at}`)}
                  </Button>
                ))}
              </div>
            </div>

            <div className="flex gap-2">
              <Input
                className="flex-1"
                label={t('character.inventory.ac_value_label')}
                type="number"
                value={form.ac_value}
                onChange={(v) => setForm((f) => ({ ...f, ac_value: v }))}
                min={1}
              />
              <Input
                className="flex-1"
                label={t('character.inventory.strength_req_label')}
                type="number"
                value={form.strength_req}
                onChange={(v) => setForm((f) => ({ ...f, strength_req: v }))}
                min={0}
              />
            </div>

            <label className="flex items-center gap-2 cursor-pointer text-sm text-dnd-text font-body">
              <input
                type="checkbox"
                checked={form.stealth_disadvantage}
                onChange={(e) => setForm((f) => ({ ...f, stealth_disadvantage: e.target.checked }))}
                className="w-5 h-5 accent-dnd-gold"
              />
              {t('character.inventory.stealth_disadvantage_label')}
            </label>
          </>
        )}

        {/* === SHIELD fields === */}
        {form.item_type === 'shield' && (
          <Input
            label={t('character.inventory.ac_bonus_label')}
            type="number"
            value={form.ac_bonus}
            onChange={(v) => setForm((f) => ({ ...f, ac_bonus: v }))}
            min={0}
          />
        )}

        {/* === CONSUMABLE fields === */}
        {(form.item_type === 'consumable' || form.item_type === 'potion' || form.item_type === 'scroll') && (
          <Input
            variant="textarea"
            label={t('character.inventory.effect_label')}
            value={form.effect}
            onChange={(v) => setForm((f) => ({ ...f, effect: v }))}
            rows={2}
          />
        )}

        {/* === TOOL fields === */}
        {form.item_type === 'tool' && (
          <Input
            label={t('character.inventory.tool_type_label')}
            value={form.tool_type}
            onChange={(v) => setForm((f) => ({ ...f, tool_type: v }))}
          />
        )}

        {/* === ABILITY MODIFIERS (all types) === */}
        <AbilityModifiersEditor
          modifiers={form.ability_modifiers ?? []}
          onChange={(next) => setForm((f) => ({ ...f, ability_modifiers: next }))}
        />

        {/* Quantity & Weight */}
        <div className="flex gap-2">
          <Input
            className="flex-1"
            label={t('character.inventory.quantity')}
            type="number"
            value={form.quantity}
            onChange={(v) => setForm((f) => ({ ...f, quantity: v }))}
            min={1}
          />
          <Input
            className="flex-1"
            label={`${t('character.inventory.weight')} (lb)`}
            type="number"
            value={form.weight}
            onChange={(v) => setForm((f) => ({ ...f, weight: v }))}
            min={0}
          />
        </div>

        {/* Description */}
        <Input
          variant="textarea"
          label={t('character.inventory.description')}
          value={form.description}
          onChange={(v) => setForm((f) => ({ ...f, description: v }))}
          placeholder={t('character.inventory.description')}
          rows={2}
        />

        <div className="flex gap-2 pt-2">
          <Button
            variant="primary"
            fullWidth
            onClick={() => onSubmit(form)}
            disabled={!isItemFormValid(form)}
            loading={isPending}
            haptic="success"
          >
            {isEditing ? t('common.save') : t('common.add')}
          </Button>
          <Button variant="secondary" fullWidth onClick={onCancel}>
            {t('common.cancel')}
          </Button>
        </div>
      </div>
    </Sheet>
  )
}

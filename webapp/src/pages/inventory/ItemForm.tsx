import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import SwitchToggle from '@/components/ui/SwitchToggle'
import WizardFooter from '@/components/ui/WizardFooter'
import DamageTypePicker from '@/components/ui/DamageTypePicker'
import DamageDiceBuilder from './DamageDiceBuilder'
import { getItemTypeIcon } from '@/lib/itemIcons'
import AbilityModifiersEditor from './AbilityModifiersEditor'
import EffectsEditor from './EffectsEditor'
import {
  ITEM_TYPES,
  WEAPON_PROPERTIES,
  ARMOR_TYPES,
  WEAPON_TYPES,
  CONSUMABLE_SUBTYPES,
  hasSingleQuantity,
  emptyForm,
  isItemFormValid,
  itemToFormData,
  type ItemFormData,
} from './itemMetadata'
import type { Item } from '@/types'
import { useUnitSettings, lbToDisplay, displayToLb, weightUnitLabel, formatWeight, oppositeSystem } from '@/store/unitSettings'

interface ItemFormProps {
  initialData?: Item | null
  onSubmit: (data: ItemFormData) => void
  onCancel: () => void
  isPending: boolean
}

type WizardStep = 'type' | 'base' | 'advanced'

export default function ItemForm({ initialData, onSubmit, onCancel, isPending }: ItemFormProps) {
  const { t } = useTranslation()
  const system = useUnitSettings((s) => s.system)
  const [form, setForm] = useState<ItemFormData>(emptyForm)
  const [step, setStep] = useState<WizardStep>('type')
  const isEditing = !!initialData

  useEffect(() => {
    if (initialData) {
      const fd = itemToFormData(initialData)
      // itemToFormData returns weight in canonical lb; show it in the active unit.
      setForm({
        ...fd,
        weight: fd.weight === '' ? '' : String(lbToDisplay(Number(fd.weight) || 0, system)),
      })
    } else {
      setForm(emptyForm)
    }
    setStep('type')
  }, [initialData, system])

  const stepIdx = step === 'type' ? 1 : step === 'base' ? 2 : 3
  const stepLabel = `${stepIdx}/3`

  const toggleProperty = (prop: string) => {
    setForm((f) => ({
      ...f,
      properties: f.properties.includes(prop)
        ? f.properties.filter((p) => p !== prop)
        : [...f.properties, prop],
    }))
  }

  const hidesQuantity = hasSingleQuantity(form.item_type)

  const canAdvanceFromType = form.name.trim().length > 0

  return (
    <Sheet
      open
      onClose={onCancel}
      title={`${isEditing ? t('common.edit') : t('character.inventory.add')} · ${stepLabel}`}
    >
      <div className="p-5 space-y-3">
        {step === 'type' && (
        <>
        {/* Name */}
        <Input
          label={t('character.inventory.item_name')}
          value={form.name}
          onChange={(v) => setForm((f) => ({ ...f, name: v }))}
          placeholder={t('character.inventory.item_name')}
        />

        {/* Type — griglia chip a selezione singola */}
        <div>
          <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
            {t('character.inventory.item_type')}
          </label>
          <div className="grid grid-cols-2 gap-2">
            {ITEM_TYPES.map((type, idx) => {
              const Icon = getItemTypeIcon(type)
              const active = form.item_type === type
              const lastSpan =
                idx === ITEM_TYPES.length - 1 && ITEM_TYPES.length % 2 === 1 ? 'col-span-2' : ''
              return (
                <button
                  key={type}
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, item_type: type }))}
                  className={`min-h-[46px] flex items-center gap-2 px-3 rounded-xl text-sm font-medium transition-colors ${lastSpan}
                    ${active
                      ? 'bg-dnd-gold text-dnd-ink shadow-halo-gold'
                      : 'bg-dnd-surface-raised text-dnd-text border border-dnd-border'}`}
                >
                  <Icon size={18} className="shrink-0" />
                  <span className="text-left leading-tight">
                    {t(`character.inventory.types.${type}`)}
                  </span>
                </button>
              )
            })}
          </div>
        </div>

        <WizardFooter
          className="pt-2"
          secondaryLabel={t('common.cancel')}
          onSecondary={onCancel}
          primaryLabel={t('common.next')}
          onPrimary={() => setStep('base')}
          primaryDisabled={!canAdvanceFromType}
          primaryHaptic="medium"
        />
        </>
        )}

        {step === 'base' && (
        <>
        {/* Quantity & Weight */}
        <div className="flex gap-2">
          {!hidesQuantity && (
            <Input
              className="flex-1"
              label={t('character.inventory.quantity')}
              type="number"
              value={form.quantity}
              onChange={(v) => setForm((f) => ({ ...f, quantity: v }))}
              min={1}
              placeholder="1"
            />
          )}
          <Input
            className="flex-1"
            label={`${t('character.inventory.weight')} (${weightUnitLabel(system)})`}
            type="number"
            value={form.weight}
            onChange={(v) => setForm((f) => ({ ...f, weight: v }))}
            min={0}
            placeholder="0"
            inputMode="decimal"
          />
        </div>
        {Number(form.weight) > 0 && (
          <p className="-mt-1 text-[10px] font-mono text-dnd-text-faint tabular-nums">
            ≈ {formatWeight(displayToLb(Number(form.weight) || 0, system), oppositeSystem(system))}
          </p>
        )}

        {/* Description */}
        <Input
          variant="textarea"
          label={t('character.inventory.description')}
          value={form.description}
          onChange={(v) => setForm((f) => ({ ...f, description: v }))}
          placeholder={t('character.inventory.description')}
          rows={3}
        />

        <WizardFooter
          className="pt-2"
          secondaryLabel={t('common.back')}
          onSecondary={() => setStep('type')}
          primaryLabel={t('common.next')}
          onPrimary={() => setStep('advanced')}
          primaryHaptic="medium"
        />
        </>
        )}

        {step === 'advanced' && (
        <>
        {/* === WEAPON fields === */}
        {form.item_type === 'weapon' && (
          <>
            <DamageDiceBuilder
              value={form.damage_dice}
              onChange={(v) => setForm((f) => ({ ...f, damage_dice: v }))}
            />

            <DamageTypePicker
              label={t('character.inventory.damage_type_label')}
              value={form.damage_type}
              onChange={(v) => setForm((f) => ({ ...f, damage_type: v }))}
              valueFormat="item"
            />

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

            <SwitchToggle
              checked={form.stealth_disadvantage}
              onChange={(v) => setForm((f) => ({ ...f, stealth_disadvantage: v }))}
              label={t('character.inventory.stealth_disadvantage_label')}
              aria-label={t('character.inventory.stealth_disadvantage_label')}
            />
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
        {form.item_type === 'consumable' && (
          <>
            <div>
              <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
                {t('character.inventory.subtype_label')}
              </label>
              <div className="grid grid-cols-2 gap-2">
                {CONSUMABLE_SUBTYPES.map((st, idx) => {
                  const active = form.subtype === st
                  // Chip-grid rule: in a 2-col grid with an odd count, the last
                  // chip spans both columns so there's no orphan gap.
                  const lastSpan =
                    idx === CONSUMABLE_SUBTYPES.length - 1 && CONSUMABLE_SUBTYPES.length % 2 === 1
                      ? 'col-span-2'
                      : ''
                  return (
                    <button
                      key={st}
                      type="button"
                      onClick={() => setForm((f) => ({ ...f, subtype: st }))}
                      className={`min-h-[44px] px-3 rounded-xl text-sm font-medium transition-colors ${lastSpan}
                        ${active
                          ? 'bg-dnd-gold text-dnd-ink shadow-halo-gold'
                          : 'bg-dnd-surface-raised text-dnd-text border border-dnd-border'}`}
                    >
                      {t(`character.inventory.subtypes.${st}`)}
                    </button>
                  )
                })}
              </div>
            </div>

            <EffectsEditor
              effects={form.effects ?? []}
              onChange={(next) => setForm((f) => ({ ...f, effects: next }))}
            />

            <Input
              variant="textarea"
              label={t('character.inventory.effect_label')}
              value={form.effect}
              onChange={(v) => setForm((f) => ({ ...f, effect: v }))}
              rows={2}
            />
          </>
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

        <WizardFooter
          className="pt-2"
          secondaryLabel={t('common.back')}
          onSecondary={() => setStep('base')}
          primaryLabel={isEditing ? t('common.save') : t('common.add')}
          onPrimary={() =>
            onSubmit({
              ...form,
              weight: String(displayToLb(Number(form.weight) || 0, system)),
              quantity: hidesQuantity && !isEditing ? '1' : form.quantity,
            })
          }
          primaryDisabled={!isItemFormValid(form)}
          primaryLoading={isPending}
          primaryHaptic="success"
        />
        </>
        )}
      </div>
    </Sheet>
  )
}

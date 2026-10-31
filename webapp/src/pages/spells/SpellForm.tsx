import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { BookOpen, RefreshCw } from 'lucide-react'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import ChipSelect from '@/components/ui/ChipSelect'
import PresetTextField from '@/components/ui/PresetTextField'
import DamageTypePicker from '@/components/ui/DamageTypePicker'
import SwitchToggle from '@/components/ui/SwitchToggle'
import DamageDiceBuilder from '@/pages/inventory/DamageDiceBuilder'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import CatalogPicker from '@/components/catalog/CatalogPicker'
import { loadCatalog, spellToForm, type Lang, type SpellEntry } from '@/lib/srd/catalog'
import { useUnitSettings } from '@/store/unitSettings'
import { parseComponents, serializeComponents, type ComponentToken } from './spellComponents'
import {
  CASTING_TIME_PRESETS,
  RANGE_PRESETS,
  DURATION_PRESETS,
  SPELL_DIE_SIZES,
  SPELL_MAX_DICE_COUNT,
  isConcentrationDuration,
} from './spellPresets'
import type { Spell } from '@/types'

export type SpellFormData = {
  name: string
  level: string
  description: string
  casting_time: string
  range_area: string
  components: string
  duration: string
  is_concentration: boolean
  is_ritual: boolean
  damage_dice: string
  damage_type: string
  attack_save: '' | 'ATK' | 'SAVE'
  higher_level: string
  school: string
  srd_index: string
  higher_levels_dice: string
}

const emptyForm: SpellFormData = {
  name: '', level: '0', description: '', casting_time: '', range_area: '',
  components: '', duration: '', is_concentration: false, is_ritual: false,
  damage_dice: '', damage_type: '', attack_save: '',
  higher_level: '', school: '', srd_index: '', higher_levels_dice: '',
}

const COMPONENT_TOKENS: readonly ComponentToken[] = ['V', 'S', 'M']

interface SpellFormProps {
  initialData?: Spell | null
  onSubmit: (data: SpellFormData) => void
  onCancel: () => void
  isPending: boolean
}

export default function SpellForm({ initialData, onSubmit, onCancel, isPending }: SpellFormProps) {
  const { t, i18n } = useTranslation()
  const lang: Lang = i18n.language?.startsWith('en') ? 'en' : 'it'
  const unitSystem = useUnitSettings((s) => s.system)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [confirmReload, setConfirmReload] = useState(false)
  const [form, setForm] = useState<SpellFormData>(emptyForm)
  const [dealsDamage, setDealsDamage] = useState(false)
  // Material detail kept aside so toggling M off/on doesn't lose the text
  // (the serialized string only carries it while M is selected).
  const [materialDraft, setMaterialDraft] = useState('')
  // Legacy components strings the V/S/M editor can't represent fall back to
  // the plain free-text input, so editing never loses data.
  const [componentsFallback, setComponentsFallback] = useState(false)
  const isEditing = !!initialData

  useEffect(() => {
    if (initialData) {
      setForm({
        name: initialData.name,
        level: String(initialData.level),
        description: initialData.description || '',
        casting_time: initialData.casting_time || '',
        range_area: initialData.range_area || '',
        components: initialData.components || '',
        duration: initialData.duration || '',
        is_concentration: initialData.is_concentration,
        is_ritual: initialData.is_ritual,
        damage_dice: initialData.damage_dice || '',
        damage_type: initialData.damage_type || '',
        attack_save: initialData.attack_save === 'ATK' || initialData.attack_save === 'SAVE' ? initialData.attack_save : '',
        higher_level: initialData.higher_level || '',
        school: initialData.school || '',
        srd_index: initialData.srd_index || '',
        higher_levels_dice: initialData.higher_levels_dice || '',
      })
      const parsed = parseComponents(initialData.components || '')
      setMaterialDraft(parsed.material)
      setComponentsFallback(!parsed.conformant)
      setDealsDamage(!!initialData.damage_dice)
    } else {
      setForm(emptyForm)
      setMaterialDraft('')
      setComponentsFallback(false)
      setDealsDamage(false)
    }
  }, [initialData])

  const handleSubmit = () => {
    onSubmit(dealsDamage ? form : { ...form, damage_dice: '', damage_type: '' })
  }

  // Catalogue prefill: overwrites the form with the entry text in the current language.
  const applyEntry = (entry: SpellEntry, only?: (keyof SpellFormData)[]) => {
    const filled = spellToForm(entry, lang, unitSystem)
    const patch = only
      ? Object.fromEntries(Object.entries(filled).filter(([k]) => only.includes(k as keyof SpellFormData)))
      : filled
    setForm((f) => ({ ...f, ...patch }))
    if (!only) {
      const parsed = parseComponents(filled.components ?? '')
      setMaterialDraft(parsed.material)
      setComponentsFallback(!parsed.conformant)
      setDealsDamage(!!filled.damage_dice)
    }
  }
  const reloadFromCatalog = async () => {
    setConfirmReload(false)
    const entry = (await loadCatalog('spells')).find((e) => e.index === form.srd_index)
    if (entry) applyEntry(entry, ['name', 'description', 'casting_time', 'range_area', 'duration', 'higher_level'])
  }

  const componentTokens = parseComponents(form.components).tokens
  const toggleComponent = (token: ComponentToken) => {
    const next = componentTokens.includes(token)
      ? componentTokens.filter((tk) => tk !== token)
      : [...componentTokens, token]
    setForm((f) => ({ ...f, components: serializeComponents(next, materialDraft) }))
  }
  const changeMaterial = (v: string) => {
    setMaterialDraft(v)
    setForm((f) => ({ ...f, components: serializeComponents(componentTokens, v) }))
  }

  const levelOptions = [
    { value: '0', label: t('character.spells.cantrip') },
    ...[1, 2, 3, 4, 5, 6, 7, 8, 9].map((l) => ({ value: String(l), label: String(l) })),
  ]

  const toggleDealsDamage = (on: boolean) => {
    setDealsDamage(on)
    // Seed the builder so the preview reflects an actual value right away.
    if (on && !form.damage_dice.trim()) setForm((f) => ({ ...f, damage_dice: '1d6' }))
  }

  return (
    <Sheet
      open
      onClose={onCancel}
      title={isEditing ? t('character.spells.edit') : t('character.spells.add')}
    >
      <div className="p-5 space-y-4">
        <Input
          label={t('character.spells.name')}
          value={form.name}
          onChange={(v) => setForm((f) => ({ ...f, name: v }))}
          placeholder={t('character.spells.name')}
        />

        <Button
          variant="secondary"
          fullWidth
          icon={form.srd_index ? <RefreshCw size={16} /> : <BookOpen size={16} />}
          onClick={() => (form.srd_index ? setConfirmReload(true) : setPickerOpen(true))}
        >
          {form.srd_index ? t('character.spells.reload_catalog') : t('character.spells.from_catalog')}
        </Button>

        <ChipSelect
          label={t('character.spells.level')}
          options={levelOptions}
          value={form.level}
          onChange={(v) => setForm((f) => ({ ...f, level: v }))}
        />

        <PresetTextField
          label={t('character.spells.casting_time')}
          presets={CASTING_TIME_PRESETS}
          value={form.casting_time}
          onChange={(v) => setForm((f) => ({ ...f, casting_time: v }))}
          customLabel={t('common.other')}
          placeholder={t('character.spells.casting_time_placeholder')}
        />

        <PresetTextField
          label={t('character.spells.range')}
          presets={RANGE_PRESETS}
          value={form.range_area}
          onChange={(v) => setForm((f) => ({ ...f, range_area: v }))}
          customLabel={t('common.other')}
          placeholder={t('character.spells.range_placeholder')}
        />

        <PresetTextField
          label={t('character.spells.duration')}
          presets={DURATION_PRESETS}
          value={form.duration}
          onChange={(v) => setForm((f) => ({
            ...f,
            duration: v,
            is_concentration: isConcentrationDuration(v) ? true : f.is_concentration,
          }))}
          customLabel={t('common.other')}
          placeholder={t('character.spells.duration_placeholder')}
        />

        {componentsFallback ? (
          <Input
            label={t('character.spells.components')}
            value={form.components}
            onChange={(v) => setForm((f) => ({ ...f, components: v }))}
            placeholder="V, S, M"
          />
        ) : (
          <div>
            <label className="block text-xs uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
              {t('character.spells.components')}
            </label>
            <div className="flex gap-2">
              {COMPONENT_TOKENS.map((token) => {
                const active = componentTokens.includes(token)
                return (
                  <Pressable
                    key={token}
                    aria-pressed={active}
                    onClick={() => toggleComponent(token)}
                    whileTap={{ scale: 0.95 }}
                    className={`min-h-[44px] min-w-[56px] px-3 rounded-xl text-sm font-bold transition-colors
                      ${active
                        ? 'bg-dnd-gold text-dnd-ink shadow-engrave'
                        : 'bg-dnd-surface-raised text-dnd-text border border-dnd-border'}`}
                  >
                    {token}
                  </Pressable>
                )
              })}
            </div>
            <p className="text-xs text-dnd-text-muted font-body italic mt-1.5">
              {t('character.spells.components_help')}
            </p>
            {componentTokens.includes('M') && (
              <Input
                className="mt-2"
                label={t('character.spells.material_detail_label')}
                value={materialDraft}
                onChange={changeMaterial}
                placeholder={t('character.spells.material_detail_placeholder')}
              />
            )}
          </div>
        )}

        <div className="space-y-3">
          <SwitchToggle
            checked={dealsDamage}
            onChange={toggleDealsDamage}
            label={t('character.spells.deals_damage')}
            aria-label={t('character.spells.deals_damage')}
          />
          {dealsDamage && (
            <>
              <DamageDiceBuilder
                value={form.damage_dice}
                onChange={(v) => setForm((f) => ({ ...f, damage_dice: v }))}
                dieSizes={SPELL_DIE_SIZES}
                maxCount={SPELL_MAX_DICE_COUNT}
                label={t('character.spells.damage_dice_label')}
              />
              <DamageTypePicker
                label={t('character.spells.damage_type_label')}
                value={form.damage_type}
                onChange={(v) => setForm((f) => ({ ...f, damage_type: v }))}
                valueFormat="spell"
                allowEmpty
              />
            </>
          )}
        </div>

        <ChipSelect
          label={t('character.spells.attack_save.label')}
          options={[
            { value: 'ATK', label: t('character.spells.attack_save.atk') },
            { value: 'SAVE', label: t('character.spells.attack_save.save') },
            { value: '', label: t('character.spells.attack_save.none') },
          ]}
          value={form.attack_save}
          onChange={(v) => setForm((f) => ({ ...f, attack_save: v as SpellFormData['attack_save'] }))}
          columns={3}
        />

        <Input
          variant="textarea"
          label={t('character.spells.description')}
          value={form.description}
          onChange={(v) => setForm((f) => ({ ...f, description: v }))}
          placeholder={t('character.spells.description')}
          rows={4}
        />

        <div className="space-y-1.5">
          <SwitchToggle
            checked={form.is_concentration}
            onChange={(v) => setForm((f) => ({ ...f, is_concentration: v }))}
            label={t('character.spells.concentration')}
            aria-label={t('character.spells.concentration')}
          />
          <SwitchToggle
            checked={form.is_ritual}
            onChange={(v) => setForm((f) => ({ ...f, is_ritual: v }))}
            label={t('character.spells.ritual')}
            aria-label={t('character.spells.ritual')}
          />
          <p className="text-xs text-dnd-text-muted font-body italic leading-snug">
            {t('character.spells.concentration_marker_help')}
          </p>
        </div>

        <div className="flex gap-2 pt-2">
          <Button variant="secondary" fullWidth onClick={onCancel}>
            {t('common.cancel')}
          </Button>
          <Button
            variant="primary"
            fullWidth
            onClick={handleSubmit}
            disabled={!form.name.trim()}
            loading={isPending}
            haptic="success"
          >
            {isEditing ? t('common.save') : t('common.add')}
          </Button>
        </div>
      </div>
      {pickerOpen && (
        <CatalogPicker
          kind="spells"
          onClose={() => setPickerOpen(false)}
          onPick={(e) => { applyEntry(e); setPickerOpen(false) }}
        />
      )}
      <ConfirmSheet
        open={confirmReload}
        onClose={() => setConfirmReload(false)}
        onConfirm={() => void reloadFromCatalog()}
        title={t('character.spells.reload_title')}
        body={t('character.spells.reload_body')}
        confirmLabel={t('character.spells.reload_confirm')}
        confirmVariant="primary"
      />
    </Sheet>
  )
}

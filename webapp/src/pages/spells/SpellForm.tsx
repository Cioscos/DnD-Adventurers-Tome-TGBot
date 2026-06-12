import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Sparkles } from 'lucide-react'
import { m } from 'framer-motion'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import ChipSelect from '@/components/ui/ChipSelect'
import PresetTextField from '@/components/ui/PresetTextField'
import DamageTypePicker from '@/components/ui/DamageTypePicker'
import SwitchToggle from '@/components/ui/SwitchToggle'
import DamageDiceBuilder from '@/pages/inventory/DamageDiceBuilder'
import { lookupSrdSpell } from '@/lib/spellSrd'
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
}

const emptyForm: SpellFormData = {
  name: '', level: '0', description: '', casting_time: '', range_area: '',
  components: '', duration: '', is_concentration: false, is_ritual: false,
  damage_dice: '', damage_type: '',
}

const COMPONENT_TOKENS: readonly ComponentToken[] = ['V', 'S', 'M']

interface SpellFormProps {
  initialData?: Spell | null
  onSubmit: (data: SpellFormData) => void
  onCancel: () => void
  isPending: boolean
}

export default function SpellForm({ initialData, onSubmit, onCancel, isPending }: SpellFormProps) {
  const { t } = useTranslation()
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

  // SRD auto-fill: when the user types a recognized spell name, propose to fill
  // empty optional fields (range, components, duration, damage). We never overwrite
  // a non-empty field the user has already touched.
  const srdMatch = !isEditing ? lookupSrdSpell(form.name) : null
  const applySrd = () => {
    if (!srdMatch) return
    setForm((f) => ({
      ...f,
      level: f.level === '0' && srdMatch.level !== 0 ? String(srdMatch.level) : f.level,
      casting_time: f.casting_time.trim() || srdMatch.casting_time || '',
      range_area: f.range_area.trim() || srdMatch.range_area || '',
      components: f.components.trim() || srdMatch.components || '',
      duration: f.duration.trim() || srdMatch.duration || '',
      damage_dice: f.damage_dice.trim() || srdMatch.damage_dice || '',
      damage_type: f.damage_type.trim() || srdMatch.damage_type || '',
      is_concentration: f.is_concentration || !!srdMatch.is_concentration,
      is_ritual: f.is_ritual || !!srdMatch.is_ritual,
    }))
    // Side states mirror the fill-if-empty rule above.
    if (!form.components.trim() && srdMatch.components) {
      const parsed = parseComponents(srdMatch.components)
      setMaterialDraft(parsed.material)
      setComponentsFallback(!parsed.conformant)
    }
    if (form.damage_dice.trim() || srdMatch.damage_dice) setDealsDamage(true)
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

        {srdMatch && (
          <button
            type="button"
            onClick={applySrd}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-xl bg-dnd-arcane/15 border border-dnd-arcane/40 text-dnd-arcane-text text-xs font-body text-left hover:bg-dnd-arcane/25 transition-colors"
          >
            <Sparkles size={14} className="text-dnd-arcane-bright shrink-0" />
            <span className="flex-1">
              {t('character.spells.srd_autofill', {
                defaultValue: 'Compila da SRD: livello, gittata, durata, componenti, danno (campi vuoti).',
              })}
            </span>
          </button>
        )}

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
            <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
              {t('character.spells.components')}
            </label>
            <div className="flex gap-2">
              {COMPONENT_TOKENS.map((token) => {
                const active = componentTokens.includes(token)
                return (
                  <m.button
                    key={token}
                    type="button"
                    aria-pressed={active}
                    onClick={() => toggleComponent(token)}
                    whileTap={{ scale: 0.95 }}
                    className={`min-h-[44px] min-w-[56px] px-3 rounded-xl text-sm font-bold transition-colors
                      ${active
                        ? 'bg-dnd-gold text-dnd-ink shadow-engrave'
                        : 'bg-dnd-surface-raised text-dnd-text border border-dnd-border'}`}
                  >
                    {token}
                  </m.button>
                )
              })}
            </div>
            <p className="text-[11px] text-dnd-text-muted font-body italic mt-1.5">
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
          <p className="text-[11px] text-dnd-text-muted font-body italic leading-snug">
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
    </Sheet>
  )
}

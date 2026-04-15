import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import DndInput from '@/components/DndInput'
import DndButton from '@/components/DndButton'
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

interface SpellFormProps {
  initialData?: Spell | null
  onSubmit: (data: SpellFormData) => void
  onCancel: () => void
  isPending: boolean
}

export default function SpellForm({ initialData, onSubmit, onCancel, isPending }: SpellFormProps) {
  const { t } = useTranslation()
  const [form, setForm] = useState<SpellFormData>(emptyForm)
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
    } else {
      setForm(emptyForm)
    }
  }, [initialData])

  const handleSubmit = () => {
    onSubmit(form)
  }

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-end z-50 p-4"
      onFocusCapture={(e) => (e.target as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'nearest' })}
    >
      <div className="w-full rounded-2xl bg-dnd-surface-elevated p-4 space-y-3 max-h-[80vh] overflow-y-auto">
        <h3 className="font-semibold font-cinzel text-dnd-gold">
          {isEditing ? t('character.spells.edit') : t('character.spells.add')}
        </h3>

        <DndInput
          label={t('character.spells.name')}
          value={form.name}
          onChange={(v) => setForm((f) => ({ ...f, name: v }))}
          placeholder={t('character.spells.name')}
        />

        <div className="flex gap-2">
          <div className="flex-1">
            <label className="block text-[11px] uppercase tracking-wider mb-1 font-medium text-dnd-gold-dim">
              {t('character.spells.level')}
            </label>
            <select
              value={form.level}
              onChange={(e) => setForm((f) => ({ ...f, level: e.target.value }))}
              className="w-full bg-dnd-surface rounded-xl px-2 py-3 min-h-[48px] outline-none text-dnd-text
                         border border-transparent focus:border-dnd-gold-dim"
            >
              <option value="0">{t('character.spells.cantrip')}</option>
              {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((l) => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
          </div>
          <DndInput
            className="flex-1"
            label={t('character.spells.casting_time')}
            value={form.casting_time}
            onChange={(v) => setForm((f) => ({ ...f, casting_time: v }))}
            placeholder="1 azione"
          />
        </div>

        <div className="flex gap-2">
          <DndInput
            className="flex-1"
            label={t('character.spells.range')}
            value={form.range_area}
            onChange={(v) => setForm((f) => ({ ...f, range_area: v }))}
            placeholder="18m"
          />
          <DndInput
            className="flex-1"
            label={t('character.spells.duration')}
            value={form.duration}
            onChange={(v) => setForm((f) => ({ ...f, duration: v }))}
            placeholder="Istantanea"
          />
        </div>

        <div className="flex gap-2">
          <DndInput
            className="flex-1"
            label={t('character.spells.components')}
            value={form.components}
            onChange={(v) => setForm((f) => ({ ...f, components: v }))}
            placeholder="V, S, M"
          />
          <DndInput
            className="flex-1"
            label={t('character.spells.damage')}
            value={form.damage_dice}
            onChange={(v) => setForm((f) => ({ ...f, damage_dice: v }))}
            placeholder="2d6"
          />
        </div>

        <div>
          <label className="block text-[11px] uppercase tracking-wider mb-1 font-medium text-dnd-gold-dim">
            {t('character.spells.description')}
          </label>
          <textarea
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            placeholder={t('character.spells.description')}
            rows={4}
            className="w-full bg-dnd-surface rounded-xl px-3 py-2 outline-none resize-none text-dnd-text
                       placeholder:text-dnd-text-secondary/50 border border-transparent
                       focus:border-dnd-gold-dim"
          />
        </div>

        <div className="flex gap-4">
          <label className="flex items-center gap-2 text-sm text-dnd-text">
            <input
              type="checkbox"
              checked={form.is_concentration}
              onChange={(e) => setForm((f) => ({ ...f, is_concentration: e.target.checked }))}
              className="w-4 h-4 accent-dnd-gold"
            />
            {t('character.spells.concentration')}
          </label>
          <label className="flex items-center gap-2 text-sm text-dnd-text">
            <input
              type="checkbox"
              checked={form.is_ritual}
              onChange={(e) => setForm((f) => ({ ...f, is_ritual: e.target.checked }))}
              className="w-4 h-4 accent-dnd-gold"
            />
            {t('character.spells.ritual')}
          </label>
        </div>

        <div className="flex gap-2">
          <DndButton
            onClick={handleSubmit}
            disabled={!form.name.trim()}
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

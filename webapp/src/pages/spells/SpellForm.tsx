import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Sparkles } from 'lucide-react'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import { lookupSrdSpell } from '@/lib/spellSrd'
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
  }

  return (
    <Sheet
      open
      onClose={onCancel}
      title={isEditing ? t('character.spells.edit') : t('character.spells.add')}
    >
      <div className="p-5 space-y-3">
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

        <div className="flex gap-2">
          <div className="flex-1">
            <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
              {t('character.spells.level')}
            </label>
            <select
              value={form.level}
              onChange={(e) => setForm((f) => ({ ...f, level: e.target.value }))}
              className="w-full px-3 py-2.5 min-h-[48px] rounded-lg bg-dnd-surface text-dnd-text
                         border-b-2 border-dnd-border outline-none font-body text-sm"
            >
              <option value="0">{t('character.spells.cantrip')}</option>
              {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((l) => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
          </div>
          <Input
            className="flex-1"
            label={t('character.spells.casting_time')}
            value={form.casting_time}
            onChange={(v) => setForm((f) => ({ ...f, casting_time: v }))}
            placeholder="1 azione"
          />
        </div>

        <div className="flex gap-2">
          <Input
            className="flex-1"
            label={t('character.spells.range')}
            value={form.range_area}
            onChange={(v) => setForm((f) => ({ ...f, range_area: v }))}
            placeholder="18m"
          />
          <Input
            className="flex-1"
            label={t('character.spells.duration')}
            value={form.duration}
            onChange={(v) => setForm((f) => ({ ...f, duration: v }))}
            placeholder="Istantanea"
          />
        </div>

        <div className="flex gap-2">
          <Input
            className="flex-1"
            label={t('character.spells.components')}
            value={form.components}
            onChange={(v) => setForm((f) => ({ ...f, components: v }))}
            placeholder="V, S, M"
          />
          <Input
            className="flex-1"
            label={t('character.spells.damage')}
            value={form.damage_dice}
            onChange={(v) => setForm((f) => ({ ...f, damage_dice: v }))}
            placeholder="2d6"
          />
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
          <div className="flex gap-4">
            <label className="flex items-center gap-2 text-sm text-dnd-text font-body cursor-pointer">
              <input
                type="checkbox"
                checked={form.is_concentration}
                onChange={(e) => setForm((f) => ({ ...f, is_concentration: e.target.checked }))}
                className="w-5 h-5 accent-dnd-gold"
              />
              {t('character.spells.concentration')}
            </label>
            <label className="flex items-center gap-2 text-sm text-dnd-text font-body cursor-pointer">
              <input
                type="checkbox"
                checked={form.is_ritual}
                onChange={(e) => setForm((f) => ({ ...f, is_ritual: e.target.checked }))}
                className="w-5 h-5 accent-dnd-gold"
              />
              {t('character.spells.ritual')}
            </label>
          </div>
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

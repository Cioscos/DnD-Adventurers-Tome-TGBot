import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import Card from '@/components/Card'
import DndInput from '@/components/DndInput'
import DndButton from '@/components/DndButton'

const PREDEFINED_CLASSES: Record<string, { hit_die: number; spellcasting_ability: string | null }> = {
  barbarian: { hit_die: 12, spellcasting_ability: null },
  bard:      { hit_die: 8,  spellcasting_ability: 'charisma' },
  cleric:    { hit_die: 8,  spellcasting_ability: 'wisdom' },
  druid:     { hit_die: 8,  spellcasting_ability: 'wisdom' },
  fighter:   { hit_die: 10, spellcasting_ability: null },
  rogue:     { hit_die: 8,  spellcasting_ability: null },
  wizard:    { hit_die: 6,  spellcasting_ability: 'intelligence' },
  monk:      { hit_die: 8,  spellcasting_ability: null },
  paladin:   { hit_die: 10, spellcasting_ability: 'charisma' },
  ranger:    { hit_die: 10, spellcasting_ability: 'wisdom' },
  sorcerer:  { hit_die: 6,  spellcasting_ability: 'charisma' },
  warlock:   { hit_die: 8,  spellcasting_ability: 'charisma' },
}

const CUSTOM_KEY = '__custom__'

type ClassForm = {
  class_key: string
  custom_name: string
  level: string
  subclass: string
  hit_die: string
  spellcasting_ability: string
}

const emptyClass: ClassForm = {
  class_key: '',
  custom_name: '',
  level: '1',
  subclass: '',
  hit_die: '8',
  spellcasting_ability: '',
}

export { PREDEFINED_CLASSES, CUSTOM_KEY, emptyClass }
export type { ClassForm }

export function resolveClassName(form: ClassForm): string {
  return form.class_key === CUSTOM_KEY ? form.custom_name.trim() : form.class_key
}

interface AddClassFormProps {
  onAdd: (form: ClassForm) => void
  onCancel: () => void
  isPending: boolean
  lockLevelTo?: number
}

export default function AddClassForm({ onAdd, onCancel, isPending, lockLevelTo }: AddClassFormProps) {
  const { t } = useTranslation()
  const [classForm, setClassForm] = useState<ClassForm>(() =>
    lockLevelTo != null ? { ...emptyClass, level: String(lockLevelTo) } : emptyClass
  )

  const isPredefined = classForm.class_key !== '' && classForm.class_key !== CUSTOM_KEY
  const predefinedAttrs = isPredefined ? PREDEFINED_CLASSES[classForm.class_key] : null
  const canAdd = classForm.class_key !== '' && (classForm.class_key !== CUSTOM_KEY || classForm.custom_name.trim() !== '')

  function handleClassKeyChange(key: string) {
    if (key === CUSTOM_KEY) {
      setClassForm((f) => ({ ...f, class_key: key }))
    } else if (PREDEFINED_CLASSES[key]) {
      const attrs = PREDEFINED_CLASSES[key]
      setClassForm((f) => ({
        ...f,
        class_key: key,
        custom_name: '',
        hit_die: String(attrs.hit_die),
        spellcasting_ability: attrs.spellcasting_ability ?? '',
      }))
    } else {
      setClassForm((f) => ({ ...f, class_key: key }))
    }
  }

  const handleSubmit = () => {
    onAdd(classForm)
    setClassForm(emptyClass)
  }

  const handleCancel = () => {
    setClassForm(emptyClass)
    onCancel()
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4">
      <Card className="w-full space-y-3">
        <h3 className="font-semibold">{t('character.multiclass.add_class')}</h3>

        {/* Class selector */}
        <select
          value={classForm.class_key}
          onChange={(e) => handleClassKeyChange(e.target.value)}
          className="w-full bg-dnd-surface rounded-xl px-3 py-2 outline-none"
        >
          <option value="" disabled>{t('character.multiclass.class_name')}</option>
          {Object.keys(PREDEFINED_CLASSES).map((key) => (
            <option key={key} value={key}>{t(`dnd.classes.${key}`)}</option>
          ))}
          <option value={CUSTOM_KEY}>{t('character.multiclass.custom_class')}</option>
        </select>

        {/* Custom class name input */}
        {classForm.class_key === CUSTOM_KEY && (
          <DndInput
            value={classForm.custom_name}
            onChange={(v) => setClassForm((f) => ({ ...f, custom_name: v }))}
            placeholder={t('character.multiclass.custom_class_name')}
          />
        )}

        <div className="flex gap-2">
          {lockLevelTo == null && (
            <div className="flex-1">
              <DndInput
                label={t('character.multiclass.level')}
                type="number"
                min={1}
                max={20}
                value={classForm.level}
                onChange={(v) => setClassForm((f) => ({ ...f, level: v }))}
              />
            </div>
          )}
          <div className="flex-1">
            <p className="block text-[11px] uppercase tracking-wider mb-1 font-medium text-dnd-gold-dim">
              {t('character.multiclass.hit_die')}
            </p>
            <select
              value={classForm.hit_die}
              disabled={!!predefinedAttrs}
              onChange={(e) => setClassForm((f) => ({ ...f, hit_die: e.target.value }))}
              className="w-full bg-dnd-surface rounded-xl px-2 py-3 min-h-[48px] outline-none disabled:opacity-60"
            >
              {[6, 8, 10, 12].map((d) => <option key={d} value={d}>d{d}</option>)}
            </select>
          </div>
        </div>

        <DndInput
          value={classForm.subclass}
          onChange={(v) => setClassForm((f) => ({ ...f, subclass: v }))}
          placeholder={t('character.multiclass.subclass')}
        />

        {/* Spellcasting ability: auto-filled and read-only for predefined classes */}
        {classForm.class_key === CUSTOM_KEY || !predefinedAttrs ? (
          <DndInput
            value={classForm.spellcasting_ability}
            onChange={(v) => setClassForm((f) => ({ ...f, spellcasting_ability: v }))}
            placeholder={t('character.multiclass.spellcasting')}
          />
        ) : (
          <p className="text-sm text-dnd-text-secondary px-1">
            {t('character.multiclass.spellcasting')}: {predefinedAttrs.spellcasting_ability ?? '\u2014'}
          </p>
        )}

        {/* Auto-resources hint for predefined classes */}
        {isPredefined && (
          <p className="text-xs text-dnd-text-secondary italic px-1">
            {t('character.multiclass.auto_resources_hint')}
          </p>
        )}

        <div className="flex gap-2">
          <DndButton
            onClick={handleSubmit}
            disabled={!canAdd}
            loading={isPending}
            className="flex-1"
          >
            {t('common.add')}
          </DndButton>
          <DndButton
            variant="secondary"
            onClick={handleCancel}
            className="flex-1"
          >
            {t('common.cancel')}
          </DndButton>
        </div>
      </Card>
    </div>
  )
}

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import Card from '@/components/Card'
import DndInput from '@/components/DndInput'
import DndButton from '@/components/DndButton'
import SelectSheet from '@/components/ui/SelectSheet'
import ChipSelect from '@/components/ui/ChipSelect'
import { useRegisterOverlay } from '@/store/overlayStore'
import { PREDEFINED_CLASSES, CUSTOM_KEY, classOptions, emptyClass, type ClassForm } from './addClass.utils'

interface AddClassFormProps {
  onAdd: (form: ClassForm) => void
  onCancel: () => void
  isPending: boolean
  lockLevelTo?: number
}

export default function AddClassForm({ onAdd, onCancel, isPending, lockLevelTo }: AddClassFormProps) {
  const { t } = useTranslation()
  useRegisterOverlay(true)
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
        <SelectSheet
          title={t('character.multiclass.class_name')}
          options={classOptions(t)}
          value={classForm.class_key}
          onChange={handleClassKeyChange}
          placeholder={t('character.multiclass.class_name')}
        />

        {/* Custom class name input */}
        {classForm.class_key === CUSTOM_KEY && (
          <DndInput
            value={classForm.custom_name}
            onChange={(v) => setClassForm((f) => ({ ...f, custom_name: v }))}
            placeholder={t('character.multiclass.custom_class_name')}
          />
        )}

        {lockLevelTo == null && (
          <DndInput
            label={t('character.multiclass.level')}
            type="number"
            min={1}
            max={20}
            value={classForm.level}
            onChange={(v) => setClassForm((f) => ({ ...f, level: v }))}
          />
        )}
        <ChipSelect
          label={t('character.multiclass.hit_die')}
          options={[6, 8, 10, 12].map((d) => ({ value: String(d), label: `d${d}` }))}
          value={classForm.hit_die}
          onChange={(v) => setClassForm((f) => ({ ...f, hit_die: v }))}
          disabled={!!predefinedAttrs}
          columns={4}
        />

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
          <p className="text-sm text-dnd-text-muted px-1">
            {t('character.multiclass.spellcasting')}: {predefinedAttrs.spellcasting_ability ?? '\u2014'}
          </p>
        )}

        {/* Auto-resources hint for predefined classes */}
        {isPredefined && (
          <p className="text-xs text-dnd-text-muted italic px-1">
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

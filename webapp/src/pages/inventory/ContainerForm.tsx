import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Pressable from '@/components/ui/Pressable'
import SwitchToggle from '@/components/ui/SwitchToggle'
import WizardFooter from '@/components/ui/WizardFooter'
import { useUnitSettings, lbToDisplay, displayToLb, weightUnitLabel } from '@/store/unitSettings'
import { PRESETS, defaultContainer, type ContainerFormValue } from '@/lib/containers'

/** Capienza (nell'unità dell'utente, salvata in lb) + i due interruttori. Condiviso con ItemForm. */
export function ContainerFields({ value, onChange }: { value: ContainerFormValue; onChange: (v: ContainerFormValue) => void }) {
  const { t } = useTranslation()
  const system = useUnitSettings((s) => s.system)
  const [cap, setCap] = useState(value.capacity_lb == null ? '' : String(lbToDisplay(value.capacity_lb, system)))
  const p = 'character.inventory.containers.'
  return (
    <div className="space-y-2">
      <Input
        label={`${t(p + 'capacity')} (${weightUnitLabel(system)})`}
        type="number"
        min={0}
        inputMode="decimal"
        value={cap}
        onChange={(v) => {
          setCap(v)
          onChange({ ...value, capacity_lb: v === '' ? null : displayToLb(Number(v) || 0, system) })
        }}
        placeholder={t(p + 'no_capacity')}
      />
      <SwitchToggle
        checked={value.counts_weight}
        onChange={(v) => onChange({ ...value, counts_weight: v })}
        label={t(p + 'counts_weight')}
        aria-label={t(p + 'counts_weight')}
      />
      <SwitchToggle
        checked={value.quick_access}
        onChange={(v) => onChange({ ...value, quick_access: v })}
        label={t(p + 'quick_access')}
        aria-label={t(p + 'quick_access')}
      />
    </div>
  )
}

interface Props {
  onSubmit: (v: { name: string; weight: number; container: ContainerFormValue }) => void
  onCancel: () => void
  isPending: boolean
}

export default function ContainerForm({ onSubmit, onCancel, isPending }: Props) {
  const { t } = useTranslation()
  const system = useUnitSettings((s) => s.system)
  const [name, setName] = useState(t('character.inventory.container.default_name'))
  const [nameTouched, setNameTouched] = useState(false)
  const [weight, setWeight] = useState('')
  const [container, setContainer] = useState<ContainerFormValue>(defaultContainer)
  const [fieldsKey, setFieldsKey] = useState(0) // rimonta i campi quando un preset cambia la capienza
  const p = 'character.inventory.containers.'

  const applyPreset = (pr: (typeof PRESETS)[number]) => {
    if (!nameTouched) setName(t(p + 'presets.' + pr.key))
    setWeight(String(lbToDisplay(pr.weight, system)))
    setContainer({ ...container, capacity_lb: pr.capacity_lb, quick_access: pr.quick_access })
    setFieldsKey((k) => k + 1)
  }

  return (
    <Sheet open onClose={onCancel} title={t(p + 'new')}>
      <div className="p-5 space-y-3">
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((pr) => (
            <Pressable
              key={pr.key}
              onClick={() => applyPreset(pr)}
              className="min-h-[44px] px-3 rounded-xl text-sm font-medium bg-dnd-surface-raised text-dnd-text border border-dnd-border"
            >
              {t(p + 'presets.' + pr.key)}
            </Pressable>
          ))}
        </div>
        <Input label={t('character.inventory.item_name')} value={name} onChange={(v) => { setName(v); setNameTouched(true) }} />
        <Input
          label={`${t('character.inventory.weight')} (${weightUnitLabel(system)})`}
          type="number"
          min={0}
          inputMode="decimal"
          value={weight}
          onChange={setWeight}
          placeholder="0"
        />
        <ContainerFields key={fieldsKey} value={container} onChange={setContainer} />
        <WizardFooter
          className="pt-2"
          secondaryLabel={t('common.cancel')}
          onSecondary={onCancel}
          primaryLabel={t('common.add')}
          onPrimary={() => onSubmit({ name: name.trim(), weight: displayToLb(Number(weight) || 0, system), container })}
          primaryDisabled={name.trim() === ''}
          primaryLoading={isPending}
          primaryHaptic="success"
        />
      </div>
    </Sheet>
  )
}

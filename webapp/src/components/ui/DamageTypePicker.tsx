import { useTranslation } from 'react-i18next'
import ChipSelect from './ChipSelect'
import { DAMAGE_TYPES } from '@/pages/inventory/itemMetadata'

interface DamageTypePickerProps {
  label?: string
  value: string
  onChange: (value: string) => void
  /** Stored value format: items use prefixed slugs ('dmg_fire'), spells use
   *  bare slugs ('fire') — see SpellDamageSheet's `dmg_` translation prefix. */
  valueFormat?: 'item' | 'spell'
  /** Re-tap on the active chip clears the value (spells may have no type). */
  allowEmpty?: boolean
  columns?: 2 | 3
  className?: string
}

/** Damage-type chip grid shared by ItemForm (weapons) and SpellForm. */
export default function DamageTypePicker({
  label,
  value,
  onChange,
  valueFormat = 'item',
  allowEmpty = false,
  columns = 2,
  className = '',
}: DamageTypePickerProps) {
  const { t } = useTranslation()

  const toStored = (slug: string) => (valueFormat === 'spell' ? slug.replace(/^dmg_/, '') : slug)
  const toSlug = (stored: string) => (valueFormat === 'spell' ? `dmg_${stored}` : stored)

  const options = DAMAGE_TYPES.map((slug) => ({
    value: toStored(slug),
    label: t(`character.inventory.damage_types.${slug}`),
  }))

  // Legacy free-text value that maps to no known slug (e.g. Italian "fuoco"):
  // keep it visible as an extra raw chip so editing never loses data.
  const trimmed = value.trim()
  const known = trimmed === '' || (DAMAGE_TYPES as readonly string[]).includes(toSlug(trimmed))
  if (!known) options.push({ value: trimmed, label: trimmed })

  const handleChange = (v: string) => {
    if (allowEmpty && v === trimmed) onChange('')
    else onChange(v)
  }

  return (
    <ChipSelect
      label={label}
      options={options}
      value={trimmed}
      onChange={handleChange}
      columns={columns}
      className={className}
    />
  )
}

import { useState } from 'react'
import { m } from 'framer-motion'
import Input from './Input'

interface PresetTextFieldProps {
  label: string
  /** Exact stored strings — chips display them as-is and match by equality,
   *  so SRD/DB values highlight the right chip on edit. */
  presets: readonly string[]
  value: string
  onChange: (value: string) => void
  /** Label of the free-text chip (pass a translated "Altro…"). */
  customLabel: string
  placeholder?: string
  className?: string
}

/** Preset chips + a "custom" chip revealing a free-text input. The value
 *  stays a free string: presets only guide, they never constrain. */
export default function PresetTextField({
  label,
  presets,
  value,
  onChange,
  customLabel,
  placeholder,
  className = '',
}: PresetTextFieldProps) {
  const trimmed = value.trim()
  const isPreset = (presets as readonly string[]).includes(trimmed)
  // Out-of-preset non-empty values (legacy/SRD-exotic) land on the custom chip
  // with their text shown, so editing never loses data.
  const [customMode, setCustomMode] = useState(false)
  const customActive = customMode || (trimmed !== '' && !isPreset)

  const pickPreset = (preset: string) => {
    setCustomMode(false)
    // Re-tap on the selected chip clears the field (placeholder-only convention).
    onChange(trimmed === preset && !customActive ? '' : preset)
  }

  const pickCustom = () => {
    setCustomMode(true)
    if (isPreset) onChange('')
  }

  const chipCls = (active: boolean) =>
    `min-h-[44px] px-3 py-2 rounded-xl text-xs font-medium transition-colors break-words
     ${active
       ? 'bg-dnd-gold text-dnd-ink shadow-halo-gold'
       : 'bg-dnd-surface-raised text-dnd-text border border-dnd-border'}`

  return (
    <div className={className}>
      <label className="block text-[11px] uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">
        {label}
      </label>
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label={label}>
        {presets.map((preset) => {
          const active = !customActive && trimmed === preset
          return (
            <m.button
              key={preset}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => pickPreset(preset)}
              whileTap={{ scale: 0.95 }}
              className={chipCls(active)}
            >
              {preset}
            </m.button>
          )
        })}
        <m.button
          type="button"
          role="radio"
          aria-checked={customActive}
          onClick={pickCustom}
          whileTap={{ scale: 0.95 }}
          className={chipCls(customActive)}
        >
          {customLabel}
        </m.button>
      </div>
      {customActive && (
        <Input
          className="mt-2"
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          autoFocus={customMode}
        />
      )}
    </div>
  )
}

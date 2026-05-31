import { useTranslation } from 'react-i18next'
import { Sparkles, Hash, Check, X } from 'lucide-react'
import type { Property } from '@/lib/homebrew/types'
import { tonePerValue, type BadgeTone } from './propertyBadge.utils'

const TONE_CLASSES: Record<BadgeTone, string> = {
  danger:
    'bg-dnd-crimson/20 border border-dnd-crimson/40 text-dnd-crimson-bright',
  success:
    'bg-dnd-emerald/20 border border-dnd-emerald/40 text-dnd-emerald-bright',
  neutral:
    'bg-dnd-chip-bg border border-dnd-chip-border/60 text-dnd-text',
}

const TONE_ICON_CLASSES: Record<BadgeTone, string> = {
  danger: 'text-dnd-crimson-bright',
  success: 'text-dnd-emerald-bright',
  neutral: 'text-dnd-gold-dim',
}

interface PropertyBadgeProps {
  propertyKey: string
  value: unknown
  property: Property
  locale: 'it' | 'en'
  /**
   * When provided, the badge becomes interactive:
   *  - boolean → toggles on tap
   *  - enum    → cycles to the next value in `property.values` on tap
   *  - number  → exposes −/+ steppers
   *  - text    → stays read-only (out of scope)
   * Without this prop the badge stays read-only (backwards compatible).
   */
  onSetProperty?: (key: string, value: unknown) => void
  /** Disables the interactive controls while a mutation is in flight. */
  disabled?: boolean
}

/** Next value in an enum's `values` ring (wraps around). */
function nextEnumValue(property: Property, value: unknown): string | null {
  const values = property.values
  if (!values || values.length === 0) return null
  const idx = values.indexOf(String(value))
  // Unknown current value → start from the first option.
  const nextIdx = idx === -1 ? 0 : (idx + 1) % values.length
  return values[nextIdx]
}

function pickIcon(property: Property, value: unknown) {
  if (property.type === 'boolean') {
    return value ? <Check size={12} /> : <X size={12} />
  }
  if (property.type === 'number') {
    return <Hash size={12} />
  }
  return <Sparkles size={12} />
}

export default function PropertyBadge({
  propertyKey,
  value,
  property,
  locale,
  onSetProperty,
  disabled = false,
}: PropertyBadgeProps) {
  const { t } = useTranslation()

  const label =
    property.label_i18n?.[locale] ??
    property.label_i18n?.['it'] ??
    property.label_i18n?.['en'] ??
    propertyKey

  let valueLabel: string
  if (property.type === 'boolean') {
    valueLabel = value ? t('common.yes') : t('common.no')
  } else if (property.type === 'enum') {
    const key = String(value)
    valueLabel =
      property.value_labels_i18n?.[key]?.[locale] ??
      property.value_labels_i18n?.[key]?.['it'] ??
      property.value_labels_i18n?.[key]?.['en'] ??
      key
  } else {
    valueLabel = String(value)
  }

  const tone = tonePerValue(property, value)
  const icon = pickIcon(property, value)

  // `text` is never editable here (out of scope); `enum` needs ≥1 candidate
  // value to cycle through. Anything else with a handler is interactive.
  const canEdit =
    !!onSetProperty &&
    property.type !== 'text' &&
    (property.type !== 'enum' || (property.values?.length ?? 0) > 0)

  const inner = (
    <>
      <span className={`shrink-0 inline-flex ${TONE_ICON_CLASSES[tone]}`}>
        {icon}
      </span>
      <span className="text-xs font-medium truncate">
        <span className="opacity-75">{label}:</span>{' '}
        <span className="font-semibold">{valueLabel}</span>
      </span>
    </>
  )

  // ---- Number: −/+ steppers (44×44 touch targets) ------------------------
  if (canEdit && property.type === 'number') {
    const num = Number(value) || 0
    const step = (delta: number) => onSetProperty!(propertyKey, num + delta)
    return (
      <div
        className={`flex items-center gap-1 rounded-lg pl-2 pr-1 py-0.5 ${TONE_CLASSES[tone]}`}
        title={`${label}: ${valueLabel}`}
      >
        <span className={`shrink-0 inline-flex ${TONE_ICON_CLASSES[tone]}`}>
          {icon}
        </span>
        <span className="text-xs font-medium truncate flex-1 min-w-0">
          <span className="opacity-75">{label}:</span>{' '}
          <span className="font-semibold tabular-nums">{valueLabel}</span>
        </span>
        <button
          type="button"
          onClick={() => step(-1)}
          disabled={disabled}
          className="w-11 h-11 -my-1.5 shrink-0 inline-flex items-center justify-center rounded-md text-current active:opacity-60 disabled:opacity-30"
          aria-label="-"
        >
          &minus;
        </button>
        <button
          type="button"
          onClick={() => step(1)}
          disabled={disabled}
          className="w-11 h-11 -my-1.5 shrink-0 inline-flex items-center justify-center rounded-md text-current active:opacity-60 disabled:opacity-30"
          aria-label="+"
        >
          +
        </button>
      </div>
    )
  }

  // ---- Boolean / enum: whole badge is a tap target -----------------------
  if (canEdit) {
    const handleTap = () => {
      if (property.type === 'boolean') {
        onSetProperty!(propertyKey, !value)
      } else {
        const next = nextEnumValue(property, value)
        if (next !== null) onSetProperty!(propertyKey, next)
      }
    }
    return (
      <button
        type="button"
        onClick={handleTap}
        disabled={disabled}
        className={`flex items-center gap-1.5 rounded-lg px-2 min-h-[44px] w-full text-left ${TONE_CLASSES[tone]} active:opacity-60 disabled:opacity-50`}
        title={`${label}: ${valueLabel}`}
      >
        {inner}
      </button>
    )
  }

  // ---- Read-only (no handler, or text) -----------------------------------
  return (
    <div
      className={`flex items-center gap-1.5 rounded-lg px-2 py-1.5 ${TONE_CLASSES[tone]}`}
      title={`${label}: ${valueLabel}`}
    >
      {inner}
    </div>
  )
}

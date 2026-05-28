import { useTranslation } from 'react-i18next'
import { Sparkles, Hash, Check, X } from 'lucide-react'
import type { Property } from '@/lib/homebrew/types'

/**
 * Semantic-Triad heuristic — flags enum values that hint at degraded /
 * cursed states (danger tone) or enhanced / blessed states (success tone).
 * Anything else stays neutral gold. Bilingual lists keep parity between
 * homebrew rules written in Italian or English.
 */
export const BAD_VALUE_TOKENS: ReadonlyArray<string> = [
  // English
  'broken',
  'damaged',
  'degraded',
  'worn',
  'ruined',
  'cursed',
  'rotten',
  'shattered',
  'poor',
  'bad',
  // Italian
  'rotta',
  'rotto',
  'danneggiata',
  'danneggiato',
  'pessima',
  'pessimo',
  'maledetta',
  'maledetto',
  'usurata',
  'usurato',
  'consumata',
  'consumato',
  'rovinata',
  'rovinato',
]

export const GOOD_VALUE_TOKENS: ReadonlyArray<string> = [
  // English
  'pristine',
  'enchanted',
  'blessed',
  'magical',
  'magic',
  'flawless',
  'perfect',
  'excellent',
  // Italian
  'integra',
  'integro',
  'incantata',
  'incantato',
  'benedetta',
  'benedetto',
  'magica',
  'magico',
  'eccellente',
  'perfetta',
  'perfetto',
]

export type BadgeTone = 'danger' | 'success' | 'neutral'

/**
 * Picks a tone for an enum property whose key suggests a state/condition
 * (quality / condition / state). Number, boolean, text always stay neutral.
 */
export function tonePerValue(property: Property, value: unknown): BadgeTone {
  if (property.type !== 'enum') return 'neutral'
  const isStateLike = /quality|condition|state/i.test(property.key)
  if (!isStateLike) return 'neutral'
  const normalized = String(value).toLowerCase()
  if (BAD_VALUE_TOKENS.includes(normalized)) return 'danger'
  if (GOOD_VALUE_TOKENS.includes(normalized)) return 'success'
  return 'neutral'
}

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

  return (
    <div
      className={`flex items-center gap-1.5 rounded-lg px-2 py-1.5 ${TONE_CLASSES[tone]}`}
      title={`${label}: ${valueLabel}`}
    >
      <span className={`shrink-0 inline-flex ${TONE_ICON_CLASSES[tone]}`}>
        {icon}
      </span>
      <span className="text-xs font-medium truncate">
        <span className="opacity-75">{label}:</span>{' '}
        <span className="font-semibold">{valueLabel}</span>
      </span>
    </div>
  )
}

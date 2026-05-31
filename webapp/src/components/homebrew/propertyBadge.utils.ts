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

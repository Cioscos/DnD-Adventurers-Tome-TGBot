import type { TFunction } from 'i18next'

/**
 * Localise a condition label for display in a pill / list.
 *
 * Exhaustion renders with its level (e.g. "Spossatezza (livello 3)") when
 * val is a positive number; all other conditions render by slug.
 */
export function formatCondition(
  key: string,
  val: unknown,
  t: TFunction,
): string {
  if (key === 'exhaustion' && typeof val === 'number' && val > 0) {
    return t('character.conditions.exhaustion', { level: val })
  }
  return t(`character.conditions.${key}`)
}

/** Preset values for the guided SpellForm fields.
 *
 *  These are LITERAL Italian DB strings, not i18n keys: the SRD autofill
 *  (`spells-srd.json`) writes Italian values regardless of the UI language,
 *  and the preset chips must byte-match them so editing an SRD-filled spell
 *  highlights the right chip. Out-of-preset values fall on the "Altro…" chip.
 */

export const CASTING_TIME_PRESETS = [
  '1 azione',
  '1 azione bonus',
  '1 reazione',
  '1 minuto',
  '10 minuti',
] as const

export const RANGE_PRESETS = [
  'Personale',
  'Contatto',
  '3 m',
  '9 m',
  '18 m',
  '36 m',
  '45 m',
] as const

export const DURATION_PRESETS = [
  'Istantanea',
  '1 round',
  '1 minuto',
  '10 minuti',
  '1 ora',
  '8 ore',
  '24 ore',
  'Concentrazione, fino a 1 minuto',
  'Concentrazione, fino a 10 minuti',
  'Concentrazione, fino a 1 ora',
] as const

/** Spell dice include the d20 (e.g. homebrew cantrips) on top of weapon dice. */
export const SPELL_DIE_SIZES = [4, 6, 8, 10, 12, 20] as const

/** Fireball alone scales to 12d6 with a 9th-level slot. */
export const SPELL_MAX_DICE_COUNT = 12

/** True for "Concentrazione, …" durations — used to auto-check the flag. */
export function isConcentrationDuration(duration: string): boolean {
  return /^concentrazione/i.test(duration.trim())
}

/**
 * Maps the canonical English-lowercase class_name (stored in DB / used by
 * AddClassForm) to the Italian title-case key used in class-progression.json.
 *
 * The JSON was originally authored in Italian to match in-game UI labels;
 * the DB stores the canonical key. This module is the single source of truth
 * for the bridge between the two.
 */
import progressionData from '@/data/class-progression.json'

export interface ProgressionRow {
  features: string
  proficiency_bonus: number
  spell_slots: number[] | null
}

const PROGRESSION = progressionData as Record<string, ProgressionRow[]>

const CLASS_NAME_TO_PROGRESSION_KEY: Record<string, string> = {
  barbarian: 'Barbaro',
  bard: 'Bardo',
  cleric: 'Chierico',
  druid: 'Druido',
  fighter: 'Guerriero',
  rogue: 'Ladro',
  wizard: 'Mago',
  monk: 'Monaco',
  paladin: 'Paladino',
  ranger: 'Ranger',
  sorcerer: 'Stregone',
  warlock: 'Warlock',
}

/** Resolve a stored class_name to the JSON key. Falls back to the original
 *  string for custom user-defined classes that may have been authored to
 *  match the JSON directly. */
export function progressionKey(className: string): string {
  if (className in CLASS_NAME_TO_PROGRESSION_KEY) {
    return CLASS_NAME_TO_PROGRESSION_KEY[className]
  }
  return className
}

/** Get the rows for a class. Returns undefined when not found. */
export function progressionRows(className: string): ProgressionRow[] | undefined {
  return PROGRESSION[progressionKey(className)]
}

/**
 * Italian labels for the most common, cross-class progression features. The
 * `features` strings in class-progression.json are authored in English; this
 * maps the recurring tokens the player sees most often (especially in the
 * HeroScreen progression preview) to their canonical Italian D&D 5e names.
 * Unmapped tokens fall back to English so we never show a wrong translation.
 * Keys are matched on the base token, ignoring any trailing " (qualifier)".
 */
const FEATURE_LABELS_IT: Record<string, string> = {
  Spellcasting: 'Incantesimi',
  'Ability Score Improvement': 'Aumento dei Punteggi di Caratteristica',
  ASI: 'Aumento Caratteristica',
  'Arcane Recovery': 'Recupero Arcano',
  'Arcane Tradition': 'Tradizione Arcana',
  'Arcane Tradition feature': 'privilegio di Tradizione Arcana',
}

/**
 * Localize a comma-separated `features` string. For non-Italian locales the
 * string is returned unchanged. Each comma-separated segment is translated
 * independently; a trailing " (qualifier)" (e.g. "(2 usi)") is preserved.
 */
export function localizeFeatures(features: string, locale: string): string {
  if (!locale.startsWith('it')) return features
  return features
    .split(', ')
    .map((segment) => {
      const match = segment.match(/^(.*?)(\s*\(.*\))?$/)
      const base = (match?.[1] ?? segment).trim()
      const suffix = match?.[2] ?? ''
      const translated = FEATURE_LABELS_IT[base]
      return translated ? `${translated}${suffix}` : segment
    })
    .join(', ')
}

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

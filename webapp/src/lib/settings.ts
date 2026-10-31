import { api } from '@/api/client'
import type { CharacterFull } from '@/types'

/** PATCH replaces the whole `settings` dict server-side, so always spread the existing one. */
export function saveSettingsPatch(
  char: Pick<CharacterFull, 'id' | 'settings'>,
  patch: Record<string, unknown>,
): Promise<CharacterFull> {
  return api.characters.update(char.id, { settings: { ...char.settings, ...patch } })
}

/** Preference keys the Settings page "reset" clears; everything else (game data
 *  like hp_rolls, senses, roll_notes, durations, advancement, hp_mode, war_caster) is kept. */
export const RESETTABLE_PREFERENCES = [
  'spell_slots_mode', 'prepared_cap_mode', 'prepared_cap_value', 'hp_auto_calc',
  'show_private_identity', 'hide_electrum', 'coin_weight', 'encumbrance_variant',
  'history_retention_mode', 'history_retention_events', 'history_retention_days', 'notifications',
] as const

export function resetPreferences(settings: Record<string, unknown> | null | undefined): Record<string, unknown> {
  const out = { ...settings }
  for (const k of RESETTABLE_PREFERENCES) delete out[k]
  return out
}

export const ROLL_NOTE_MAX = 120

export function rollNoteOf(char: Pick<CharacterFull, 'settings'>, key: string): string {
  const notes = char.settings?.roll_notes as Record<string, string> | undefined
  return notes?.[key] ?? ''
}

import { api } from '@/api/client'
import type { CharacterFull } from '@/types'

/** PATCH replaces the whole `settings` dict server-side, so always spread the existing one. */
export function saveSettingsPatch(
  char: Pick<CharacterFull, 'id' | 'settings'>,
  patch: Record<string, unknown>,
): Promise<CharacterFull> {
  return api.characters.update(char.id, { settings: { ...char.settings, ...patch } })
}

export const ROLL_NOTE_MAX = 120

export function rollNoteOf(char: Pick<CharacterFull, 'settings'>, key: string): string {
  const notes = char.settings?.roll_notes as Record<string, string> | undefined
  return notes?.[key] ?? ''
}

import type { CharacterFull } from '@/types'

/** Specchio di `rest_needs_hp` del server: a 0 PF non si riposa (lungo; in 2024 anche il breve). */
export function restNeedsHp(
  char: Pick<CharacterFull, 'current_hit_points' | 'hit_points' | 'rules_edition'>,
  restType: 'long' | 'short',
): boolean {
  if (restType === 'short' && char.rules_edition !== '2024') return false
  return char.current_hit_points <= 0 && char.hit_points > 0
}

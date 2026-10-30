import type { CharacterSummary } from '@/types'

export type CardStatus = 'dead' | 'unconfigured' | 'down' | 'ok'

/** PF massimi effettivi: base + modificatore homebrew. */
export function effectiveHpMax(c: CharacterSummary): number {
  return c.hit_points + c.hp_max_homebrew_modifier
}

/** CA effettiva: base + modificatore homebrew. */
export function effectiveAc(c: CharacterSummary): number {
  return c.ac + c.ac_homebrew_modifier
}

/** Stato della card in home. Morto vince su tutto; PF massimi a 0 = non configurato. */
export function cardStatus(c: CharacterSummary): CardStatus {
  if (c.is_dead) return 'dead'
  if (effectiveHpMax(c) <= 0) return 'unconfigured'
  if (c.current_hit_points === 0) return 'down'
  return 'ok'
}

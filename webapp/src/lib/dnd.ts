/** D&D 5e math helpers shared across pages. */

export function profBonus(level: number): number {
  return Math.floor((Math.max(1, level) - 1) / 4) + 2
}

export function mod(score: number): number {
  return Math.floor((score - 10) / 2)
}

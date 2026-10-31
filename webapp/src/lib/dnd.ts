/** D&D 5e math helpers shared across pages. */

export function profBonus(level: number): number {
  return Math.floor((Math.max(1, level) - 1) / 4) + 2
}

export function mod(score: number): number {
  return Math.floor((score - 10) / 2)
}

/** Cantrip damage dice multiplier by total character level (mirrors core/game/stats.py). */
export function cantripMultiplier(totalLevel: number): number {
  if (totalLevel >= 17) return 4
  if (totalLevel >= 11) return 3
  return totalLevel >= 5 ? 2 : 1
}

/** "1d10" -> "2d10" at level 5; leaves flat bonuses (e.g. "1d6+2") and unparsable input untouched. */
export function scaleCantripDice(dice: string, totalLevel: number): string {
  const m = /^(\d+)d(\d+)([+-]\d+)?$/i.exec(dice.trim())
  return m ? `${Number(m[1]) * cantripMultiplier(totalLevel)}d${m[2]}${m[3] ?? ''}` : dice
}

export function totalLevelOf(classes: { level: number }[] | undefined): number {
  return (classes ?? []).reduce((s, c) => s + c.level, 0)
}

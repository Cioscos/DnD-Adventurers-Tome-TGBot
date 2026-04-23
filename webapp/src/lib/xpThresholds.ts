/**
 * D&D 5e experience-point thresholds (SRD).
 * Index `i` = XP required to reach level `i + 1`.
 * Index 0 (= 0) is the baseline for level 1.
 */
export const XP_THRESHOLDS: readonly number[] = [
  0,
  300, 900, 2700, 6500, 14000,
  23000, 34000, 48000, 64000, 85000,
  100000, 120000, 140000, 165000, 195000,
  225000, 265000, 305000, 355000,
] as const

/** Derive the current character level from accumulated XP (capped at 20). */
export function levelFromXp(xp: number): number {
  let level = 1
  for (let i = 1; i < XP_THRESHOLDS.length; i++) {
    if (xp >= XP_THRESHOLDS[i]) level = i + 1
    else break
  }
  return Math.min(level, 20)
}

/** XP threshold needed to reach `currentLevel + 1`. Null if at cap. */
export function getNextLevelThreshold(currentLevel: number): number | null {
  return XP_THRESHOLDS[currentLevel] ?? null
}

/**
 * Quick-XP button amounts, proportional to XP remaining until the next level.
 *
 * Formula: 2% / 7% / 20% / 50% of `xpToNext`, rounded to multiples of 10,
 * with a minimum of 5 XP per button; adjacent duplicates after rounding are
 * removed so bottom-range progressions (e.g. xpToNext=50) collapse gracefully.
 *
 * Returns an empty array if `xpToNext <= 0` (character is at max level).
 */
export function quickXpAmounts(xpToNext: number): number[] {
  if (xpToNext <= 0) return []
  const PCTS = [0.02, 0.07, 0.20, 0.50] as const
  const MIN_AMOUNT = 5
  const raw = PCTS.map((p) => Math.max(MIN_AMOUNT, Math.round((p * xpToNext) / 10) * 10))
  return raw.filter((v, i) => i === 0 || v !== raw[i - 1])
}

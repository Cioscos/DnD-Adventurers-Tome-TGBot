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

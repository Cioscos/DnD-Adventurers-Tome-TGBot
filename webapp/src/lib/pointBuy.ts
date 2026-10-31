export const ABILITIES = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma'] as const
export type Ability = (typeof ABILITIES)[number]
export type Scores = Record<Ability, number>

export const STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]
export const POINT_BUY_BUDGET = 27
const COSTS: Record<number, number> = { 8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9 }

/** 5e point-buy cost; NaN outside 8-15. */
export const pointBuyCost = (score: number): number => COSTS[score] ?? NaN

export const pointBuyTotal = (scores: number[]): number =>
  scores.reduce((sum, s) => sum + pointBuyCost(s), 0)

/** Sum of four d6 minus the lowest. */
export const roll4d6DropLowest = (values: number[]): number =>
  values.reduce((a, b) => a + b, 0) - Math.min(...values)

/** Assign `value` to `ability`; if another ability holds it, they swap so the array stays a permutation. */
export function assignFromArray(current: Scores, ability: Ability, value: number): Scores {
  const holder = ABILITIES.find((a) => a !== ability && current[a] === value)
  return { ...current, ...(holder ? { [holder]: current[ability] } : {}), [ability]: value }
}

export type ScoreMode = 'array' | 'pointbuy' | 'roll' | 'manual'

export const defaultScores = (v = 10): Scores =>
  Object.fromEntries(ABILITIES.map((a) => [a, v])) as Scores
export const arrayScores = (pool = STANDARD_ARRAY): Scores =>
  Object.fromEntries(ABILITIES.map((a, i) => [a, pool[i]])) as Scores

/** Only point-buy can be invalid (over budget); the other modes stay within 3-20. */
export function scoresValid(mode: ScoreMode, s: Scores): boolean {
  if (mode !== 'pointbuy') return true
  const total = pointBuyTotal(Object.values(s))
  return !Number.isNaN(total) && total <= POINT_BUY_BUDGET
}

import { describe, it, expect } from 'vitest'
import {
  pointBuyCost, pointBuyTotal, STANDARD_ARRAY, roll4d6DropLowest, assignFromArray,
} from '@/lib/pointBuy'

describe('pointBuy', () => {
  it('costs per score', () => {
    const costs = [8, 9, 10, 11, 12, 13, 14, 15].map(pointBuyCost)
    expect(costs).toEqual([0, 1, 2, 3, 4, 5, 7, 9])
    expect(pointBuyCost(7)).toBeNaN()
    expect(pointBuyCost(16)).toBeNaN()
  })
  it('totals 27 for 15,15,15,8,8,8', () => {
    expect(pointBuyTotal([15, 15, 15, 8, 8, 8])).toBe(27)
  })
  it('standard array', () => {
    expect(STANDARD_ARRAY).toEqual([15, 14, 13, 12, 10, 8])
  })
  it('4d6 drops the lowest', () => {
    expect(roll4d6DropLowest([1, 6, 5, 4])).toBe(15)
    expect(roll4d6DropLowest([3, 3, 3, 3])).toBe(9)
  })
  it('array assignment keeps each value used once (swap on conflict)', () => {
    const cur = { strength: 15, dexterity: 14, constitution: 13, intelligence: 12, wisdom: 10, charisma: 8 }
    const next = assignFromArray(cur, 'charisma', 15)
    expect(next.charisma).toBe(15)
    expect(next.strength).toBe(8)
    expect([...Object.values(next)].sort()).toEqual([...STANDARD_ARRAY].map(String).sort().map(Number).sort())
  })
})

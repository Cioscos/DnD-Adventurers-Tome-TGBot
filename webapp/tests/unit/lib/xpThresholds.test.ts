import { describe, it, expect } from 'vitest'
import {
  XP_THRESHOLDS,
  levelFromXp,
  getNextLevelThreshold,
  quickXpAmounts,
} from '@/lib/xpThresholds'

describe('XP_THRESHOLDS — SRD table', () => {
  it('has 20 entries, starts at 0, and ends at 355000', () => {
    expect(XP_THRESHOLDS.length).toBe(20)
    expect(XP_THRESHOLDS[0]).toBe(0)
    expect(XP_THRESHOLDS[1]).toBe(300)
    expect(XP_THRESHOLDS[19]).toBe(355000)
  })
})

describe('levelFromXp', () => {
  it('returns 1 below the first threshold', () => {
    expect(levelFromXp(0)).toBe(1)
    expect(levelFromXp(299)).toBe(1)
  })

  it('crosses to the next level exactly at the threshold', () => {
    expect(levelFromXp(300)).toBe(2)
    expect(levelFromXp(899)).toBe(2)
    expect(levelFromXp(900)).toBe(3)
  })

  it('caps at level 20', () => {
    expect(levelFromXp(355000)).toBe(20)
    expect(levelFromXp(10_000_000)).toBe(20)
  })
})

describe('getNextLevelThreshold', () => {
  it('returns the XP needed for the next level', () => {
    expect(getNextLevelThreshold(1)).toBe(300)
    expect(getNextLevelThreshold(2)).toBe(900)
    expect(getNextLevelThreshold(19)).toBe(355000)
  })

  it('returns null at the level cap (20)', () => {
    expect(getNextLevelThreshold(20)).toBeNull()
  })
})

describe('quickXpAmounts', () => {
  it('returns [] when already at max level', () => {
    expect(quickXpAmounts(0)).toEqual([])
    expect(quickXpAmounts(-100)).toEqual([])
  })

  it('returns 2%/7%/20%/50% rounded to multiples of 10', () => {
    expect(quickXpAmounts(1000)).toEqual([20, 70, 200, 500])
  })

  it('collapses adjacent duplicates and enforces the 5 XP minimum', () => {
    // 1→5, 3.5→5 (dup dropped), 10→10, 25→30 ⇒ [5, 10, 30]
    expect(quickXpAmounts(50)).toEqual([5, 10, 30])
  })
})

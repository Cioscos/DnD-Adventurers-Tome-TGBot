import { describe, it, expect } from 'vitest'
import { profBonus, mod } from '@/lib/dnd'

describe('profBonus — D&D 5e proficiency bonus by level', () => {
  it('is +2 across levels 1–4', () => {
    for (const lvl of [1, 2, 3, 4]) expect(profBonus(lvl)).toBe(2)
  })

  it('steps up every 4 levels (5→+3, 9→+4, 13→+5, 17→+6)', () => {
    expect(profBonus(5)).toBe(3)
    expect(profBonus(8)).toBe(3)
    expect(profBonus(9)).toBe(4)
    expect(profBonus(12)).toBe(4)
    expect(profBonus(13)).toBe(5)
    expect(profBonus(16)).toBe(5)
    expect(profBonus(17)).toBe(6)
    expect(profBonus(20)).toBe(6)
  })

  it('clamps levels below 1 to the level-1 value (+2)', () => {
    expect(profBonus(0)).toBe(2)
    expect(profBonus(-5)).toBe(2)
  })
})

describe('mod — ability score modifier', () => {
  it('matches the canonical D&D 5e table', () => {
    expect(mod(1)).toBe(-5)
    expect(mod(8)).toBe(-1)
    expect(mod(9)).toBe(-1)
    expect(mod(10)).toBe(0)
    expect(mod(11)).toBe(0)
    expect(mod(12)).toBe(1)
    expect(mod(20)).toBe(5)
    expect(mod(30)).toBe(10)
  })

  it('floors toward negative infinity for odd low scores', () => {
    expect(mod(7)).toBe(-2)
    expect(mod(3)).toBe(-4)
  })
})

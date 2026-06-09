import { describe, it, expect } from 'vitest'
import { toRoman } from '@/lib/roman'

describe('toRoman', () => {
  it('maps 1..9 to roman numerals (used for class level chips)', () => {
    expect(toRoman(1)).toBe('I')
    expect(toRoman(2)).toBe('II')
    expect(toRoman(3)).toBe('III')
    expect(toRoman(4)).toBe('IV')
    expect(toRoman(5)).toBe('V')
    expect(toRoman(6)).toBe('VI')
    expect(toRoman(7)).toBe('VII')
    expect(toRoman(8)).toBe('VIII')
    expect(toRoman(9)).toBe('IX')
  })

  it('falls back to the plain number outside 1..9', () => {
    // D&D characters can reach level 20, beyond the single-digit roman table.
    expect(toRoman(0)).toBe('0')
    expect(toRoman(10)).toBe('10')
    expect(toRoman(20)).toBe('20')
    expect(toRoman(-1)).toBe('-1')
  })
})

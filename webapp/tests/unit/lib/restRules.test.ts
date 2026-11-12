import { describe, expect, it } from 'vitest'
import { restNeedsHp } from '@/lib/restRules'

const c = (cur: number, max: number, ed: '2014' | '2024') => ({ current_hit_points: cur, hit_points: max, rules_edition: ed })

describe('restNeedsHp', () => {
  it('lungo a 0 PF e bloccato in entrambe le edizioni', () => {
    expect(restNeedsHp(c(0, 20, '2014'), 'long')).toBe(true)
    expect(restNeedsHp(c(0, 20, '2024'), 'long')).toBe(true)
  })
  it('breve a 0 PF e bloccato solo nel 2024', () => {
    expect(restNeedsHp(c(0, 20, '2014'), 'short')).toBe(false)
    expect(restNeedsHp(c(0, 20, '2024'), 'short')).toBe(true)
  })
  it('con PF o senza massimo non blocca', () => {
    expect(restNeedsHp(c(1, 20, '2024'), 'long')).toBe(false)
    expect(restNeedsHp(c(0, 0, '2024'), 'long')).toBe(false)
  })
})

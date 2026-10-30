import { describe, it, expect } from 'vitest'
import { cardStatus, effectiveHpMax, effectiveAc } from '@/lib/characterStatus'
import type { CharacterSummary } from '@/types'

const base = (over: Partial<CharacterSummary>): CharacterSummary => ({
  id: 1, name: 'A', hit_points: 10, current_hit_points: 10, temp_hp: 0, ac: 12,
  total_level: 1, class_summary: '', heroic_inspiration: false, experience_points: 0,
  hp_max_homebrew_modifier: 0, ac_homebrew_modifier: 0, is_dead: false,
  ...over,
})

describe('cardStatus', () => {
  it('dead wins even with hit_points 0', () => {
    expect(cardStatus(base({ is_dead: true, hit_points: 0, current_hit_points: 0 }))).toBe('dead')
  })
  it('hit_points 0 and modifier 0 is unconfigured', () => {
    expect(cardStatus(base({ hit_points: 0, current_hit_points: 0 }))).toBe('unconfigured')
  })
  it('hit_points 0 with modifier 5 and current 0 is down', () => {
    expect(cardStatus(base({ hit_points: 0, hp_max_homebrew_modifier: 5, current_hit_points: 0 }))).toBe('down')
  })
  it('current 0 is down, current 4 is ok', () => {
    expect(cardStatus(base({ current_hit_points: 0 }))).toBe('down')
    expect(cardStatus(base({ current_hit_points: 4 }))).toBe('ok')
  })
})

describe('effective values', () => {
  it('adds homebrew modifiers', () => {
    const c = base({ hit_points: 20, hp_max_homebrew_modifier: 5, ac: 15, ac_homebrew_modifier: 2 })
    expect(effectiveHpMax(c)).toBe(25)
    expect(effectiveAc(c)).toBe(17)
  })
})

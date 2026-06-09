import { describe, it, expect } from 'vitest'
import { eventLabel, actionLabel } from '@/lib/homebrew/i18n-dsl'
import type { Effect, Filter } from '@/lib/homebrew/types'

describe('eventLabel', () => {
  it('returns the localized default label (it/en)', () => {
    expect(eventLabel('hp_healed', [], 'it')).toContain('curato')
    expect(eventLabel('hp_healed', [], 'en')).toContain('healed')
  })

  it('specializes attack_rolled into fumble / critical variants by filter', () => {
    const fumble: Filter[] = [{ path: '$event.is_fumble', op: 'eq', value: true }]
    const crit: Filter[] = [{ path: '$event.is_critical', op: 'eq', value: true }]
    expect(eventLabel('attack_rolled', fumble, 'it')).toContain('fallimento critico')
    expect(eventLabel('attack_rolled', crit, 'en')).toContain('critical')
  })

  it('specializes damage_taken into the critical-hit variant', () => {
    const f: Filter[] = [{ path: '$event.was_critical_hit', op: 'eq', value: true }]
    expect(eventLabel('damage_taken', f, 'it')).toContain('colpo critico')
  })
})

describe('actionLabel', () => {
  it('describes heal / damage / condition effects', () => {
    expect(actionLabel({ action: 'heal_character', amount: 5 } as Effect, 'it')).toContain('Curati')
    expect(actionLabel({ action: 'damage_character', amount: 3 } as Effect, 'en')).toContain('damage')
    expect(actionLabel({ action: 'apply_condition', key: 'poisoned' } as Effect, 'it')).toContain('condizione')
  })

  it('describes a roll_dice effect with its notation and store name', () => {
    const eff: Effect = { action: 'roll_dice', notation: '2d6', store_as: 'fireball' }
    const label = actionLabel(eff, 'it')
    expect(label).toContain('2d6')
    expect(label).toContain('fireball')
  })
})

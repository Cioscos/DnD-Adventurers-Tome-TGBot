import { describe, it, expect } from 'vitest'
import type { Effect, RuleDSL, Trigger } from '@/lib/homebrew/types'

// types.ts is a pure type mirror of the backend DSL — this is a type-smoke test:
// it fails to compile if the discriminated union / RuleDSL shape drifts, and
// asserts the constructed discriminators at runtime.
describe('homebrew DSL types', () => {
  it('a heal effect and a rule can be constructed with the expected shape', () => {
    const eff: Effect = { action: 'heal_character', amount: 5 }
    const trigger: Trigger = { event: 'hp_healed', filters: [], effects: [eff] }
    const dsl: RuleDSL = { version: 1, subject: { type: 'character' }, triggers: [trigger] }

    expect(eff.action).toBe('heal_character')
    expect(dsl.version).toBe(1)
    expect(dsl.triggers?.[0].effects[0].action).toBe('heal_character')
  })

  it('covers a representative spread of effect discriminators', () => {
    const effects: Effect[] = [
      { action: 'roll_dice', notation: '1d20', store_as: 'r' },
      { action: 'notify', severity: 'info', message: 'hi' },
      { action: 'apply_condition', key: 'poisoned' },
      { action: 'unequip', target: 'subject' },
    ]
    expect(effects.map((e) => e.action)).toEqual(['roll_dice', 'notify', 'apply_condition', 'unequip'])
  })
})

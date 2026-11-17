import { describe, it, expect } from 'vitest'
import { turnLeftovers } from '@/lib/turnLeftovers'
import type { TurnBlock } from '@/types'

const block = (over: Partial<TurnBlock>): TurnBlock => ({
  action_used: false, bonus_used: false, reaction_used: false, attacks_made: 0, action_attacks: 0,
  extra_actions: 0, once_per_turn: [], spell_slot_cast: false, bonus_spell_cast: false, free_interaction_used: false,
  ...over,
})

describe('turnLeftovers', () => {
  it('senza dati del turno non segnala niente', () => {
    expect(turnLeftovers(undefined)).toEqual({ attacksLeft: 0, actionUnused: false })
  })
  it('azione mai usata', () => {
    expect(turnLeftovers({ turn: block({}), attacks_allowed: 2 })).toEqual({ attacksLeft: 0, actionUnused: true })
  })
  it('attacco extra non fatto: 1 di 2', () => {
    expect(turnLeftovers({ turn: block({ action_attacks: 1 }), attacks_allowed: 2 })).toEqual({ attacksLeft: 1, actionUnused: false })
  })
  it('azione usata per altro o attacchi finiti: niente da dire', () => {
    expect(turnLeftovers({ turn: block({ action_used: true }), attacks_allowed: 2 })).toEqual({ attacksLeft: 0, actionUnused: false })
    expect(turnLeftovers({ turn: block({ action_attacks: 2 }), attacks_allowed: 2 })).toEqual({ attacksLeft: 0, actionUnused: false })
  })
  it('una azione extra ancora da spendere conta come azione non usata', () => {
    expect(turnLeftovers({ turn: block({ action_used: true, extra_actions: 1 }), attacks_allowed: 1 }).actionUnused).toBe(true)
  })
})

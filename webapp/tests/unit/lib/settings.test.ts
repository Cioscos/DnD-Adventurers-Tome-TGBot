import { describe, expect, it } from 'vitest'
import { resetPreferences } from '@/lib/settings'

describe('resetPreferences', () => {
  it('clears preference keys and keeps character data', () => {
    const out = resetPreferences({
      hide_electrum: true, coin_weight: true, notifications: { x: false }, spell_slots_mode: 'manual',
      hp_rolls: { 1: [6] }, senses: { darkvision: 60 }, roll_notes: { a: 'b' },
      condition_durations: { poisoned: 2 }, concentration_rounds_left: 3,
      concentration_item_spell: { item_id: 1 }, advancement: 'milestone', hp_mode: 'rolled', war_caster: true,
    })
    expect(out).toEqual({
      hp_rolls: { 1: [6] }, senses: { darkvision: 60 }, roll_notes: { a: 'b' },
      condition_durations: { poisoned: 2 }, concentration_rounds_left: 3,
      concentration_item_spell: { item_id: 1 }, advancement: 'milestone', hp_mode: 'rolled', war_caster: true,
    })
  })

  it('handles missing settings', () => {
    expect(resetPreferences(undefined)).toEqual({})
  })
})

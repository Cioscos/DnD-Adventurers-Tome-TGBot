import { describe, it, expect } from 'vitest'
import { weaponOptions } from '@/lib/weaponOptions'

describe('weaponOptions', () => {
  it('flags versatile only with a versatile die, thrown from the property', () => {
    expect(weaponOptions({ item_metadata: { properties: ['prop_versatile'] } }).versatile).toBe(false)
    expect(weaponOptions({ item_metadata: { properties: ['prop_versatile'], versatile_dice: '1d10' } }).versatile).toBe(true)
    expect(weaponOptions({ item_metadata: { properties: ['prop_thrown'] } }).thrown).toBe(true)
    expect(weaponOptions({}).thrown).toBe(false)
  })
})

describe('weaponOptions — Combattente a Due Armi 2014 (PR 3)', () => {
  const sword = (id: number) => ({ id, item_type: 'weapon', is_equipped: true, item_metadata: { properties: [] } })
  const char = (feats: string[]) => ({
    classes: [], rules_edition: '2014', ability_scores: [], items: [sword(1), sword(2)],
    abilities: feats.map((k) => ({ feature_key: k })),
  }) as never

  it('offers the other hand with two non-light one-handed weapons only with the feat', () => {
    expect(weaponOptions(sword(2), char([])).offhand).toBe(false)
    expect(weaponOptions(sword(2), char(['feat.dual_wielder'])).offhand).toBe(true)
  })

  it('never with a two-handed weapon', () => {
    const great = { id: 2, item_type: 'weapon', is_equipped: true, item_metadata: { properties: ['prop_two_handed'] } }
    expect(weaponOptions(great, char(['feat.dual_wielder'])).offhand).toBe(false)
  })
})

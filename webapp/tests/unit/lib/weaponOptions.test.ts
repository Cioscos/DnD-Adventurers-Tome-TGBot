import { describe, it, expect } from 'vitest'
import { weaponOptions, weaponPreviewText, weaponRangeFt } from '@/lib/weaponOptions'

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

describe('weaponOptions — Combattente a Due Armi: solo armi da mischia (PR 3)', () => {
  it('a ranged one-handed weapon is not a second weapon', () => {
    const sword = { id: 1, item_type: 'weapon', is_equipped: true, item_metadata: { properties: [] } }
    const crossbow = { id: 2, item_type: 'weapon', is_equipped: true, item_metadata: { properties: [], weapon_type: 'ranged' } }
    const char = { classes: [], rules_edition: '2014', ability_scores: [], items: [sword, crossbow],
      abilities: [{ feature_key: 'feat.dual_wielder' }] } as never
    expect(weaponOptions(sword, char).offhand).toBe(false)
  })
})

describe('weaponPreviewText', () => {
  it('mostra bonus per colpire e danno con il segno', () => {
    expect(weaponPreviewText({ item_metadata: { damage_dice: '1d6' }, attack_preview: { to_hit: 7, damage: 4 } })).toBe('+7 · 1d6+4')
    expect(weaponPreviewText({ item_metadata: { damage_dice: '1d4' }, attack_preview: { to_hit: -1, damage: 0 } })).toBe('-1 · 1d4')
  })
  it('vuoto senza anteprima del server', () => {
    expect(weaponPreviewText({ item_metadata: { damage_dice: '1d6' } })).toBe('')
  })
})

describe('weaponRangeFt (PA1)', () => {
  const CATALOG = [
    { index: 'longbow', name: { en: 'Longbow', it: 'Arco lungo' }, weapon_range: 'ranged', range_ft: 150, thrown_range_ft: null },
    { index: 'dagger', name: { en: 'Dagger', it: 'Pugnale' }, weapon_range: 'melee', range_ft: 5, thrown_range_ft: 20 },
  ]
  it('reads the normal range of a ranged weapon by catalog index or by name', () => {
    expect(weaponRangeFt({ item_metadata: { weapon_type: 'ranged', srd_index: 'longbow' } }, CATALOG)).toBe(150)
    expect(weaponRangeFt({ name: 'Arco lungo', item_metadata: { weapon_type: 'ranged' } }, CATALOG)).toBe(150)
  })
  it('a thrown weapon gives its thrown range; a melee one or an unknown one none', () => {
    expect(weaponRangeFt({ name: 'Dagger', item_metadata: { weapon_type: 'melee', properties: ['prop_thrown'] } }, CATALOG)).toBe(20)
    expect(weaponRangeFt({ name: 'Dagger', item_metadata: { weapon_type: 'melee' } }, CATALOG)).toBeNull()
    expect(weaponRangeFt({ name: 'Arco di Corvo', item_metadata: { weapon_type: 'ranged' } }, CATALOG)).toBeNull()
  })
})

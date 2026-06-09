import { describe, it, expect } from 'vitest'
import {
  ALL_SLOTS,
  ITEM_TYPE_TO_SLOTS,
  slotsAllowedFor,
  isSlotAllowed,
  isTwoHanded,
  handsConflict,
} from '@/lib/equipmentSlots'
import type { EquipmentSlot, Item } from '@/types'

function mkItem(p: Partial<Item>): Item {
  return {
    id: 1,
    item_type: 'weapon',
    is_equipped: false,
    equipment_slot: null,
    item_metadata: null,
    ...p,
  } as unknown as Item
}

describe('ITEM_TYPE_TO_SLOTS — contract with backend EQUIPMENT_SLOT_COMPAT', () => {
  // This mapping MUST mirror api/services/equipment.py::EQUIPMENT_SLOT_COMPAT.
  it('matches the backend item_type → slots mapping exactly', () => {
    expect(ITEM_TYPE_TO_SLOTS).toEqual({
      weapon: ['main_hand', 'off_hand'],
      armor: ['body'],
      shield: ['off_hand'],
      accessory: ['neck', 'cloak', 'ring1', 'ring2'],
      gear: ['head', 'hands', 'feet', 'ammunition'],
    })
  })

  it('only references slots that exist in ALL_SLOTS', () => {
    const all = new Set<EquipmentSlot>(ALL_SLOTS)
    expect(ALL_SLOTS).toHaveLength(11)
    for (const slots of Object.values(ITEM_TYPE_TO_SLOTS)) {
      for (const s of slots) expect(all.has(s)).toBe(true)
    }
  })
})

describe('slotsAllowedFor / isSlotAllowed', () => {
  it('returns the allowed slots for a known type', () => {
    expect(slotsAllowedFor('weapon')).toEqual(['main_hand', 'off_hand'])
    expect(slotsAllowedFor('armor')).toEqual(['body'])
  })

  it('returns [] for an unknown type', () => {
    expect(slotsAllowedFor('totally-unknown')).toEqual([])
  })

  it('isSlotAllowed gates by the mapping', () => {
    expect(isSlotAllowed('weapon', 'main_hand')).toBe(true)
    expect(isSlotAllowed('weapon', 'off_hand')).toBe(true)
    expect(isSlotAllowed('armor', 'head')).toBe(false)
    expect(isSlotAllowed('shield', 'off_hand')).toBe(true)
  })
})

describe('isTwoHanded', () => {
  it('is false for null/undefined and non-weapons', () => {
    expect(isTwoHanded(null)).toBe(false)
    expect(isTwoHanded(undefined)).toBe(false)
    expect(
      isTwoHanded(mkItem({ item_type: 'armor', item_metadata: { properties: ['prop_two_handed'] } })),
    ).toBe(false)
  })

  it('is true only for a weapon carrying the prop_two_handed property', () => {
    expect(
      isTwoHanded(mkItem({ item_type: 'weapon', item_metadata: { properties: ['prop_two_handed'] } })),
    ).toBe(true)
    expect(
      isTwoHanded(mkItem({ item_type: 'weapon', item_metadata: { properties: ['prop_finesse'] } })),
    ).toBe(false)
    expect(isTwoHanded(mkItem({ item_type: 'weapon', item_metadata: null }))).toBe(false)
  })
})

describe('handsConflict — two-handed ⇄ off-hand displacement', () => {
  const greataxe = mkItem({
    id: 10,
    item_type: 'weapon',
    is_equipped: true,
    equipment_slot: 'main_hand',
    item_metadata: { properties: ['prop_two_handed'] },
  })
  const shield = mkItem({ id: 20, item_type: 'shield' })

  it('equipping in off_hand conflicts with an equipped two-handed main_hand weapon', () => {
    expect(handsConflict([greataxe], shield, 'off_hand')).toBe(greataxe)
  })

  it('no conflict when the main_hand weapon is one-handed', () => {
    const longsword = mkItem({
      id: 11,
      item_type: 'weapon',
      is_equipped: true,
      equipment_slot: 'main_hand',
      item_metadata: { properties: [] },
    })
    expect(handsConflict([longsword], shield, 'off_hand')).toBeNull()
  })

  it('equipping a two-handed weapon in main_hand displaces the off_hand occupant', () => {
    const equippedShield = mkItem({
      id: 21,
      item_type: 'shield',
      is_equipped: true,
      equipment_slot: 'off_hand',
    })
    const twoHander = mkItem({
      id: 12,
      item_type: 'weapon',
      item_metadata: { properties: ['prop_two_handed'] },
    })
    expect(handsConflict([equippedShield], twoHander, 'main_hand')).toBe(equippedShield)
  })

  it('no conflict for unrelated slots', () => {
    expect(handsConflict([greataxe], shield, 'head')).toBeNull()
  })
})

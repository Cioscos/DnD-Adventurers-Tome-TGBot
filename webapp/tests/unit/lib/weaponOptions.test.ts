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

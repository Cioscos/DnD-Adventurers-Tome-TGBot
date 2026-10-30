import { describe, it, expect } from 'vitest'
import { applyDamageModifier, type DamageModifier } from '@/lib/damageModifier'

describe('applyDamageModifier', () => {
  it.each<[number, DamageModifier, number]>([
    [15, 'half', 7],
    [1, 'half', 0],
    [15, 'double', 30],
    [15, null, 15],
  ])('applyDamageModifier(%i, %s) = %i', (value, mod, expected) => {
    expect(applyDamageModifier(value, mod)).toBe(expected)
  })
})

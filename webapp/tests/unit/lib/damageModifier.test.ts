import { describe, it, expect } from 'vitest'
import {
  applyDamageModifier, canonicalDamageType, damageMultiplier, damagePreviewText, damageTypeLabel,
  type DamageModifier,
} from '@/lib/damageModifier'

describe('applyDamageModifier', () => {
  it.each<[number, DamageModifier, number]>([
    [15, 'half', 7],
    [1, 'half', 0],
    [15, 'double', 30],
    [15, null, 15],
    [15, 'none', 15],
    [15, 'immune', 0],
  ])('applyDamageModifier(%i, %s) = %i', (value, mod, expected) => {
    expect(applyDamageModifier(value, mod)).toBe(expected)
  })
})

describe('canonicalDamageType', () => {
  it.each(['Fuoco', 'fire', 'dmg_fire', ' FIRE ', 'Fire'])('%s -> fire', (v) => {
    expect(canonicalDamageType(v)).toBe('fire')
  })
  it('maps Italian labels and rejects unknown', () => {
    expect(canonicalDamageType('Taglio')).toBe('slashing')
    expect(canonicalDamageType('Radiante')).toBe('radiant')
    expect(canonicalDamageType('Danni non magici')).toBeNull()
    expect(canonicalDamageType(null)).toBeNull()
  })
})

describe('damageMultiplier', () => {
  const mods = { resistances: ['Fuoco'], immunities: ['cold'], vulnerabilities: ['dmg_acid'] }
  it('resolves each kind, legacy labels included', () => {
    expect(damageMultiplier(mods, 'fire')).toBe('half')
    expect(damageMultiplier(mods, 'cold')).toBe('immune')
    expect(damageMultiplier(mods, 'acid')).toBe('double')
    expect(damageMultiplier(mods, 'force')).toBe('none')
    expect(damageMultiplier(undefined, 'fire')).toBe('none')
    expect(damageMultiplier(mods, null)).toBe('none')
  })
  it('resistance + vulnerability cancel; immunity wins', () => {
    expect(damageMultiplier({ resistances: ['fire'], vulnerabilities: ['Fuoco'] }, 'fire')).toBe('none')
    expect(damageMultiplier({ resistances: ['fire'], immunities: ['fire'] }, 'fire')).toBe('immune')
  })
})

describe('labels and preview', () => {
  const t = (k: string) => (k.endsWith('dmg_fire') ? 'Fuoco' : k)
  it('translates slugs and keeps legacy free text', () => {
    expect(damageTypeLabel(t, 'fire')).toBe('Fuoco')
    expect(damageTypeLabel(t, 'Danni non magici')).toBe('Danni non magici')
  })
  it('formats the preview line', () => {
    expect(damagePreviewText('Resistenza', 14, applyDamageModifier(14, 'half'))).toBe('Resistenza: 14 → 7')
    expect(damagePreviewText(null, 15, 7)).toBe('15 → 7')
  })
})

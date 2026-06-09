import { describe, it, expect } from 'vitest'
import { martialArtsDie, unarmedDamageDice } from '@/lib/unarmedStrike'

// Contract mirror of core/game/attacks.py::martial_arts_die.
// Both sides MUST agree, otherwise the Actions page shows the wrong damage die.
describe('martialArtsDie — Monk Martial Arts die scaling', () => {
  it('is empty for non-monk level 0 or below', () => {
    expect(martialArtsDie(0)).toBe('')
    expect(martialArtsDie(-3)).toBe('')
  })

  it('scales 1d4 → 1d6 → 1d8 → 1d10 at the SRD breakpoints', () => {
    expect(martialArtsDie(1)).toBe('1d4')
    expect(martialArtsDie(4)).toBe('1d4')
    expect(martialArtsDie(5)).toBe('1d6')
    expect(martialArtsDie(10)).toBe('1d6')
    expect(martialArtsDie(11)).toBe('1d8')
    expect(martialArtsDie(16)).toBe('1d8')
    expect(martialArtsDie(17)).toBe('1d10')
    expect(martialArtsDie(20)).toBe('1d10')
  })
})

describe('unarmedDamageDice', () => {
  it('returns flat "1" for no classes or non-monks', () => {
    expect(unarmedDamageDice(undefined)).toBe('1')
    expect(unarmedDamageDice([])).toBe('1')
    expect(unarmedDamageDice([{ class_name: 'fighter', level: 5 }])).toBe('1')
  })

  it('returns the Martial Arts die for a Monk (Italian or English label)', () => {
    expect(unarmedDamageDice([{ class_name: 'monk', level: 1 }])).toBe('1d4')
    expect(unarmedDamageDice([{ class_name: 'Monaco', level: 5 }])).toBe('1d6')
  })

  it('matches the Monk label case-insensitively, ignoring surrounding whitespace', () => {
    expect(unarmedDamageDice([{ class_name: '  MONACO ', level: 11 }])).toBe('1d8')
  })

  it('uses the Monk level even in a multiclass list', () => {
    expect(
      unarmedDamageDice([
        { class_name: 'wizard', level: 3 },
        { class_name: 'monk', level: 17 },
      ]),
    ).toBe('1d10')
  })
})

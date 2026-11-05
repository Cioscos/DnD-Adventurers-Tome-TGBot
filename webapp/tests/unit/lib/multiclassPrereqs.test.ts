import { describe, it, expect } from 'vitest'
import { MULTICLASS_PREREQS, multiclassWarnings, type AbilityKey } from '@/data/multiclassPrereqs'

const scores = (over: Partial<Record<AbilityKey, number>>) => (a: AbilityKey) => over[a] ?? 10

describe('multiclassWarnings (D2)', () => {
  it('warns about the new class and about each owned class with unmet requirements', () => {
    // Monaco posseduto (DES 13 e SAG 13) con DES 14 e SAG 10; si aggiunge Mago (INT 13) con INT 8.
    const w = multiclassWarnings('wizard', ['monk'], scores({ dexterity: 14, wisdom: 10, intelligence: 8 }))
    expect(w.map((x) => x.classKey)).toEqual(['wizard', 'monk'])
    expect(w[1].groups).toEqual([{ abilities: ['wisdom'], min: 13 }])
  })

  it('warns only about the owned class when the new one is satisfied', () => {
    const w = multiclassWarnings('wizard', ['monk'], scores({ dexterity: 14, wisdom: 10, intelligence: 14 }))
    expect(w.map((x) => x.classKey)).toEqual(['monk'])
  })

  it('has no warning when every class is satisfied, and ignores custom or repeated classes', () => {
    const ok = scores({ strength: 14, charisma: 14, dexterity: 14, wisdom: 14, intelligence: 14 })
    expect(multiclassWarnings('paladin', ['fighter', null, 'fighter', 'paladin'], ok)).toEqual([])
  })
})

describe('Paladino (D6)', () => {
  it('requires Strength 13 and Charisma 13 in both editions', () => {
    expect(MULTICLASS_PREREQS.paladin).toEqual([
      { abilities: ['strength'], min: 13 }, { abilities: ['charisma'], min: 13 },
    ])
    const w = multiclassWarnings('paladin', [], scores({ strength: 15, charisma: 12 }))
    expect(w).toEqual([{ classKey: 'paladin', groups: [{ abilities: ['charisma'], min: 13 }] }])
    expect(multiclassWarnings('paladin', [], scores({ strength: 12, charisma: 15 }))[0].groups)
      .toEqual([{ abilities: ['strength'], min: 13 }])
  })
})

import { describe, it, expect } from 'vitest'
import races from '@/data/srd/races.json'
import { buildSpecies, type RaceEntry } from '@/lib/species'

const dwarf = (races.items as unknown as RaceEntry[]).find((r) => r.index === 'dwarf')!

describe('buildSpecies', () => {
  it('merges hill dwarf', () => {
    const p = buildSpecies(dwarf, dwarf.subraces[0], 'it')
    expect(p.name).toBe('Nano delle colline')
    expect(p.speed_ft).toBe(25)
    expect(p.ability_bonuses).toEqual({ con: 2, wis: 1 })
    expect(p.senses).toEqual([{ type: 'darkvision', range_ft: 60 }])
    expect(p.roll_notes['save.constitution']).toMatch(/veleno/)
    expect(p.languages).toEqual(['Comune', 'Nanico'])
    expect(p.traits.map((x) => x.name)).toContain('Robustezza nanica')
  })
  it('english notes and no subrace', () => {
    const p = buildSpecies(dwarf, null, 'en')
    expect(p.name).toBe('Dwarf')
    expect(p.roll_notes['save.constitution']).toMatch(/poison/)
    expect(p.ability_bonuses).toEqual({ con: 2 })
  })
})

import backgrounds from '@/data/srd/backgrounds.json'
import { SKILL_KEYS, backgroundLanguages, backgroundSkills, creationExtras } from '@/lib/species'

describe('creation extras', () => {
  const scores = { strength: 15, dexterity: 14, constitution: 13, intelligence: 12, wisdom: 10, charisma: 8 }
  it('sends displayed scores even if untouched, omits them only when skipped', () => {
    expect(creationExtras({ scores, skipped: false, species: null, skills: [] })).toEqual({ ability_scores: scores })
    expect(creationExtras({ scores, skipped: true, species: null, skills: [] })).toEqual({})
  })
  it('sends skills as booleans', () => {
    expect(creationExtras({ scores, skipped: true, species: null, skills: ['insight'] }).skills).toEqual({ insight: true })
  })
})

describe('background mapping', () => {
  it('every real catalogue skill maps to a known key', () => {
    for (const b of backgrounds.items) {
      const mapped = backgroundSkills(b.skill_proficiencies)
      expect(mapped).toHaveLength(b.skill_proficiencies.length)
      mapped.forEach((k) => expect(SKILL_KEYS).toContain(k))
    }
  })
  it('maps dashes and drops unknown skills', () => {
    expect(backgroundSkills(['sleight-of-hand', 'bogus'])).toEqual(['sleight_of_hand'])
  })
  it('localises fixed background languages', () => {
    expect(backgroundLanguages(['dwarvish', 'Sylvan'], 'it')).toEqual(['Nanico', 'Sylvan'])
    expect(backgroundLanguages(undefined, 'it')).toEqual([])
  })
})

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

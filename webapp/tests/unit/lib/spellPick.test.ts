import { describe, it, expect } from 'vitest'
import { spellPickFilter } from '@/lib/spellPick'
import { loadCatalog, type SpellEntry } from '@/lib/srd/catalog'

const names = (rows: SpellEntry[]) => rows.map((s) => s.index).sort()

describe('spellPickFilter', () => {
  it('a school pick (Wizard Savant) offers only spells of that school', async () => {
    const spells = await loadCatalog('spells')
    const rows = spells.filter(spellPickFilter({ max_level: 2, list: 'wizard', school: 'abjuration' }))
    expect(rows.length).toBeGreaterThan(3)
    expect(rows.every((s) => s.school === 'abjuration' && s.level <= 2)).toBe(true)
  })

  it('a cantrip pick from the druid list offers the druid cantrips and nothing else', async () => {
    const spells = await loadCatalog('spells')
    const rows = spells.filter(spellPickFilter({ max_level: 0, list: 'druid' }))
    expect(names(rows)).toEqual(['druidcraft', 'guidance', 'mending', 'poison-spray', 'produce-flame', 'resistance', 'shillelagh'])
  })

  it('never offers a leveled spell or a cantrip of another class for a cantrip pick', async () => {
    const spells = await loadCatalog('spells')
    const filter = spellPickFilter({ max_level: 0, list: 'druid' })
    expect(filter(spells.find((s) => s.index === 'fireball')!)).toBe(false)
    expect(filter(spells.find((s) => s.index === 'fire-bolt')!)).toBe(false)
  })

  it('a pick from any class stops at the highest level and keeps every class', async () => {
    const spells = await loadCatalog('spells')
    const rows = spells.filter(spellPickFilter({ max_level: 3, list: null }))
    expect(rows.length).toBeGreaterThan(50)
    expect(rows.every((s) => s.level <= 3)).toBe(true)
    expect(rows.some((s) => s.index === 'fireball')).toBe(true)
    expect(rows.some((s) => s.level === 4)).toBe(false)
  })

  it('an exact-level pick (Mystic Arcanum) offers only spells of that level', async () => {
    const spells = await loadCatalog('spells')
    const rows = spells.filter(spellPickFilter({ max_level: 6, exact: true }))
    expect(rows.length).toBeGreaterThan(5)
    expect(rows.every((s) => s.level === 6)).toBe(true)
  })

  it('a ritual pick (Book of Ancient Secrets) offers only first-level rituals', async () => {
    const spells = await loadCatalog('spells')
    const rows = spells.filter(spellPickFilter({ max_level: 1, exact: true, ritual: true }))
    expect(rows.some((s) => s.index === 'detect-magic')).toBe(true)
    expect(rows.every((s) => s.level === 1 && s.ritual)).toBe(true)
    expect(rows.some((s) => s.index === 'magic-missile')).toBe(false)
  })

  it('a list that the catalogue does not know leaves only the level limit', () => {
    const odd = { index: 'x', level: 0, classes: undefined } as unknown as SpellEntry
    expect(spellPickFilter({ max_level: 0, list: 'druid' })(odd)).toBe(false)
    expect(spellPickFilter({ max_level: 0, list: null })(odd)).toBe(true)
  })
})

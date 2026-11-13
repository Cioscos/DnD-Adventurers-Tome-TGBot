import { describe, it, expect } from 'vitest'
import { featsFor } from '@/lib/feats'
import type { CharacterFull } from '@/types'

const char = (cha = 13, level = 1, edition: '2014' | '2024' = '2024') => ({
  rules_edition: edition, total_level: level, classes: [],
  ability_scores: ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']
    .map((name) => ({ name, value: name === 'charisma' ? cha : 10 })),
}) as unknown as CharacterFull

const keys = (list: { key: string }[]) => list.map((f) => f.key)

describe('featsFor', () => {
  it('creation offers only the 10 origin feats', () => {
    const list = featsFor(null, '2024', 'creation', 'it')
    expect(list).toHaveLength(10)
    expect(keys(list)).toContain('2024_tough')
    expect(keys(list)).not.toContain('2024_actor')
  })

  it('manual ignores the level 4 minimum but keeps ability prerequisites and hides epic boons below 19', () => {
    expect(featsFor(char(13), '2024', 'manual', 'it').find((f) => f.key === '2024_actor')?.unmet).toBe(false)
    expect(featsFor(char(12), '2024', 'manual', 'it').find((f) => f.key === '2024_actor')?.unmet).toBe(true)
    expect(keys(featsFor(char(13), '2024', 'manual', 'it'))).not.toContain('2024_boon_fate')
    expect(keys(featsFor(char(13, 19), '2024', 'manual', 'it'))).toContain('2024_boon_fate')
  })

  it('a level choice offers general and origin feats, no boons', () => {
    const list = keys(featsFor(char(13, 4), '2024', 'level', 'it'))
    expect(list).toContain('2024_actor')
    expect(list).toContain('2024_alert')
    expect(list).not.toContain('2024_boon_fate')
  })

  it('2014 lists the 2014 feats', () => {
    expect(keys(featsFor(char(13, 4, '2014'), '2014', 'manual', 'it'))).toContain('alert')
  })

  it('repeatable feats carry their flag and the choices they need', () => {
    const skilled = featsFor(null, '2024', 'creation', 'it').find((f) => f.key === '2024_skilled')
    expect(skilled?.repeatable).toBe(true)
    expect(skilled?.needs).toEqual(['picks'])
  })
})

const withClass = (className: string, level: number, extra: Partial<CharacterFull> = {}) => ({
  ...char(13, level), classes: [{ class_name: className, level, options: {} }],
  general_proficiencies: { armor: [], weapons: [], tools: [], other: [] }, abilities: [], ...extra,
}) as unknown as CharacterFull

describe('featsFor — Stili e addestramento (PR 2)', () => {
  it('fighting style feats need the Fighting Style feature', () => {
    expect(featsFor(withClass('fighter', 4), '2024', 'level', 'it').find((f) => f.key === '2024_fs_defense')?.unmet).toBe(false)
    expect(featsFor(withClass('wizard', 4), '2024', 'level', 'it').find((f) => f.key === '2024_fs_defense')?.unmet).toBe(true)
    expect(featsFor(withClass('paladin', 1), '2024', 'level', 'it').find((f) => f.key === '2024_fs_defense')?.unmet).toBe(true)
  })

  it('a style already chosen by the class is unmet', () => {
    const fighter = withClass('fighter', 4, { classes: [{ class_name: 'fighter', level: 4, options: { fighting_style: ['archery'] } }] } as never)
    expect(featsFor(fighter, '2024', 'level', 'it').find((f) => f.key === '2024_fs_archery')?.unmet).toBe(true)
  })

  it('armor feats need the previous training', () => {
    const find = (c: CharacterFull) => featsFor(c, '2024', 'level', 'it').find((f) => f.key === '2024_heavily_armored')?.unmet
    expect(find(withClass('wizard', 4, { settings: { proficiencies_seeded: true }, general_proficiencies: { armor: [], weapons: ['Armi semplici'], tools: [], other: [] } } as never))).toBe(true)
    expect(find(withClass('cleric', 4, { general_proficiencies: { armor: ['Armature medie'], weapons: [], tools: [], other: [] } } as never))).toBe(false)
  })
})

describe('featsFor — addestramento come il server (revisione PR 2)', () => {
  const find = (c: CharacterFull) => featsFor(c, '2024', 'level', 'it').find((f) => f.key === '2024_heavily_armored')?.unmet
  it('a custom class passes the armor prerequisite', () => {
    expect(find(withClass('Cavaliere delle rune', 4, { general_proficiencies: { armor: [], weapons: ['Armi semplici'], tools: [], other: [] } } as never))).toBe(false)
  })
  it('a character never seeded with no proficiencies passes, a seeded one does not', () => {
    expect(find(withClass('wizard', 4))).toBe(false)
    expect(find(withClass('wizard', 4, { settings: { proficiencies_seeded: true } } as never))).toBe(true)
  })
})

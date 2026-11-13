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

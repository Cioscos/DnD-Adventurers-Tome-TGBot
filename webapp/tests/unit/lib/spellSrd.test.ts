import { describe, it, expect, vi } from 'vitest'

/**
 * `spellSrd.ts` builds a flat name→entry index at module load from
 * `@/data/spells-srd.json` (canonical key + every alias, both lowercased), and
 * skips `_`-prefixed metadata keys. We mock the JSON so the test pins the
 * indexing/lookup *logic* (case-insensitive, alias resolution, trim,
 * underscore-skip) independent of the real data file.
 *
 * The mock factory must be hoisted (vi.mock) before the spellSrd import so the
 * module's load-time `buildIndex()` sees the fixture.
 */
vi.mock('@/data/spells-srd.json', () => ({
  default: {
    _meta: { source: 'PHB', note: 'ignored metadata block' },
    'fire bolt': {
      level: 0,
      damage_dice: '1d10',
      damage_type: 'fire',
      aliases: ['Dardo di Fuoco'],
    },
    'magic missile': { level: 1, aliases: [] },
    shield: { level: 1 }, // no aliases key at all
  },
}))

import { lookupSrdSpell, srdSpellNames } from '@/lib/spellSrd'

describe('lookupSrdSpell', () => {
  it('matches the canonical key case-insensitively', () => {
    const spell = lookupSrdSpell('Fire Bolt')
    expect(spell).not.toBeNull()
    expect(spell?.level).toBe(0)
    expect(spell?.damage_dice).toBe('1d10')
    expect(spell?.damage_type).toBe('fire')
  })

  it('resolves an Italian alias case-insensitively', () => {
    const spell = lookupSrdSpell('dardo di fuoco')
    expect(spell?.damage_dice).toBe('1d10') // same entry as "fire bolt"
  })

  it('trims surrounding whitespace before matching', () => {
    expect(lookupSrdSpell('  Magic Missile  ')?.level).toBe(1)
  })

  it('returns null for an unknown name', () => {
    expect(lookupSrdSpell('Teleport')).toBeNull()
  })

  it('returns null for an empty / whitespace-only name', () => {
    expect(lookupSrdSpell('')).toBeNull()
    expect(lookupSrdSpell('   ')).toBeNull()
  })

  it('does not index `_`-prefixed metadata keys', () => {
    expect(lookupSrdSpell('_meta')).toBeNull()
  })

  it('handles entries without an aliases array', () => {
    expect(lookupSrdSpell('shield')?.level).toBe(1)
  })
})

describe('srdSpellNames', () => {
  it('returns every canonical key + alias, excluding metadata, sorted', () => {
    const names = srdSpellNames()
    expect(names).toContain('fire bolt')
    expect(names).toContain('Dardo di Fuoco')
    expect(names).toContain('magic missile')
    expect(names).toContain('shield')
    expect(names).not.toContain('_meta')
    // 3 canonical keys + 1 alias = 4 distinct names.
    expect(names).toHaveLength(4)
    // Sorted with the same default comparator the implementation uses.
    expect(names).toEqual([...names].sort())
  })
})

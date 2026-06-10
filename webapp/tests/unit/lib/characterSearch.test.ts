import { describe, it, expect } from 'vitest'
import { normalize, searchCharacter, MIN_QUERY_LENGTH } from '@/lib/characterSearch'
import type { CharacterFull } from '@/types'

function makeChar(partial: Partial<CharacterFull>): CharacterFull {
  return {
    id: 7,
    name: 'Eroe',
    hit_points: 10,
    spells: [],
    items: [],
    abilities: [],
    ...partial,
  } as CharacterFull
}

const spell = (id: number, name: string, level = 1) =>
  ({ id, name, level, is_concentration: false, is_ritual: false, is_pinned: false, is_prepared: true })

const item = (id: number, name: string, quantity = 1) =>
  ({ id, name, weight: 0, quantity, item_type: 'generic', is_equipped: false })

const ability = (id: number, name: string) =>
  ({ id, name, is_passive: false, is_active: true, restoration_type: 'none', is_class_feature: false })

describe('normalize', () => {
  it('lowercases and strips diacritics', () => {
    expect(normalize('Pozione di Velocità')).toBe('pozione di velocita')
    expect(normalize('PALLA DI FUOCO')).toBe('palla di fuoco')
  })
})

describe('searchCharacter', () => {
  it('returns nothing under the minimum query length', () => {
    const char = makeChar({ spells: [spell(1, 'Palla di Fuoco', 3)] })
    expect(searchCharacter(char, 'p')).toEqual([])
    expect(MIN_QUERY_LENGTH).toBe(2)
  })

  it('matches accent-insensitively across categories', () => {
    const char = makeChar({
      spells: [spell(1, 'Palla di Fuoco', 3)],
      items: [item(2, 'Pozione di Velocità', 3)],
      abilities: [ability(3, 'Scatto di Velocità')],
      notes: { 'Diario': 'abbiamo trovato la velocita del drago' },
    })
    const results = searchCharacter(char, 'velocita')
    expect(results.map((r) => r.type)).toEqual(['item', 'ability', 'note'])
    expect(results[0].title).toBe('Pozione di Velocità')
    expect(results[0].meta).toEqual({ quantity: 3 })
  })

  it('builds the spell focus deep-link and exposes the level', () => {
    const char = makeChar({ spells: [spell(42, 'Palla di Fuoco', 3)] })
    const [r] = searchCharacter(char, 'fuoco')
    expect(r.route).toBe('/char/7/spells?focus=42')
    expect(r.meta).toEqual({ spellLevel: 3 })
  })

  it('routes items, abilities and notes to their pages', () => {
    const char = makeChar({
      items: [item(1, 'Corda di seta')],
      abilities: [ability(2, 'Attacco extra di seta')],
      notes: { 'Trama di seta': 'testo' },
    })
    const routes = searchCharacter(char, 'seta').map((r) => r.route)
    expect(routes).toEqual(['/char/7/inventory', '/char/7/abilities', '/char/7/notes'])
  })

  it('caps results at 8 per category', () => {
    const spells = Array.from({ length: 12 }, (_, i) => spell(i, `Magia ${i}`))
    const char = makeChar({ spells })
    expect(searchCharacter(char, 'magia')).toHaveLength(8)
  })

  it('matches note bodies, not only titles', () => {
    const char = makeChar({ notes: { 'Sessione 3': 'incontrato il lich Vecna' } })
    const [r] = searchCharacter(char, 'vecna')
    expect(r.type).toBe('note')
    expect(r.title).toBe('Sessione 3')
  })

  // Le note create dalla webapp sono salvate dal BE nel formato dict
  // {body, created_at, updated_at, tags} — non stringhe (api/routers/notes.py).
  describe('dict-shaped notes (current backend format)', () => {
    it('does not throw when a dict note title does not match the query', () => {
      const char = makeChar({
        notes: { 'Diario': { body: 'testo qualunque', created_at: '2026-06-01', tags: [] } },
      })
      expect(() => searchCharacter(char, 'xy')).not.toThrow()
    })

    it('matches the body of a dict-shaped note', () => {
      const char = makeChar({
        notes: { 'Sessione 3': { body: 'incontrato il lich Vecna', tags: ['png'] } },
      })
      const [r] = searchCharacter(char, 'vecna')
      expect(r.type).toBe('note')
      expect(r.title).toBe('Sessione 3')
    })

    it('matches voice notes by title only, never by their [VOICE:] body', () => {
      const char = makeChar({
        notes: { 'Memo del vecna': { body: '[VOICE:7/abc.webm]', created_at: '2026-06-01' } },
      })
      expect(searchCharacter(char, 'vecna')).toHaveLength(1)
      expect(searchCharacter(char, 'voice')).toHaveLength(0)
      expect(searchCharacter(char, 'webm')).toHaveLength(0)
    })

    it('tolerates malformed note values without throwing', () => {
      const char = makeChar({
        notes: {
          'Numero': 42,
          'Nullo': null,
          'Senza body': { tags: ['vuota'] },
        } as never,
      })
      expect(() => searchCharacter(char, 'xy')).not.toThrow()
      const [r] = searchCharacter(char, 'senza')
      expect(r.title).toBe('Senza body')
    })
  })
})

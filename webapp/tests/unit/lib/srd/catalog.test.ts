import { describe, it, expect } from 'vitest'
import {
  loadCatalog, localized, searchCatalog, spellToForm, upcastExtraDice, type SpellEntry,
} from '@/lib/srd/catalog'

const find = async (index: string) => (await loadCatalog('spells')).find((e) => e.index === index) as SpellEntry

describe('catalog', () => {
  it('loads and caches every kind', async () => {
    const a = await loadCatalog('spells')
    expect(a.length).toBeGreaterThan(300)
    expect(await loadCatalog('spells')).toBe(a)
    for (const k of ['magic-items', 'equipment', 'races', 'backgrounds', 'feats', 'monsters'] as const) {
      expect((await loadCatalog(k)).length).toBeGreaterThan(0)
    }
  })

  it('localized falls back to English and flags it', () => {
    expect(localized({ en: 'Fire', it: 'Fuoco' }, 'it')).toEqual({ text: 'Fuoco', fallback: false })
    expect(localized({ en: 'Fire' }, 'it')).toEqual({ text: 'Fire', fallback: true })
    expect(localized({ en: 'Fire', it: 'Fuoco' }, 'en')).toEqual({ text: 'Fire', fallback: false })
    expect(localized(undefined, 'it').text).toBe('')
  })

  it('search finds "palla" and "fireball", ignoring accents and case', async () => {
    const all = await loadCatalog('spells')
    expect(searchCatalog(all, 'PALLA', 'it').map((e) => e.index)).toContain('fireball')
    expect(searchCatalog(all, 'fireball', 'it').map((e) => e.index)).toContain('fireball')
    expect(searchCatalog(all, 'liberta', 'it').length).toBeGreaterThan(0) // libertà accent-insensitive
    expect(searchCatalog(all, '', 'it')).toBe(all)
  })

  it('spellToForm builds Italian strings, metric range and srd fields', async () => {
    const f = spellToForm(await find('fireball'), 'it', 'metric')
    expect(f).toMatchObject({
      name: 'Palla di fuoco', level: '3', casting_time: '1 azione', duration: 'Istantanea',
      damage_dice: '8d6', damage_type: 'fire', attack_save: 'SAVE', school: 'evocation',
      srd_index: 'fireball', higher_levels_dice: '1d6',
    })
    expect(f.range_area).toBe('45 m (sfera 6 m)')
    expect(f.components).toMatch(/^V, S, M \(/)
    expect(spellToForm(await find('fireball'), 'en', 'imperial').range_area).toBe('150 ft (sphere 20 ft)')
  })

  it('tolerates healing and no-attack spells; sleep never prefills upcast dice', async () => {
    expect(spellToForm(await find('cure-wounds'), 'it', 'imperial')).toMatchObject({ damage_dice: '', damage_type: '', attack_save: '' })
    expect(spellToForm(await find('magic-missile'), 'it', 'imperial')).toMatchObject({ damage_dice: '3d4+3', attack_save: '' })
    const sleep = spellToForm(await find('sleep'), 'it', 'imperial')
    expect(sleep.damage_dice).toBe('5d8')
    expect(sleep.higher_levels_dice).toBe('')
  })

  it('upcastExtraDice mirrors the server rule', () => {
    const fb = { level: 3, higher_levels_dice: '1d6', srd_index: 'fireball' }
    expect(upcastExtraDice(fb, 5, 6)).toBe(2)
    expect(upcastExtraDice(fb, 3, 6)).toBe(0)
    expect(upcastExtraDice(fb, 5, 8)).toBe(0)
    expect(upcastExtraDice({ ...fb, srd_index: 'sleep' }, 5, 6)).toBe(0)
    expect(upcastExtraDice({ level: 0, higher_levels_dice: '1d6' }, 5, 6)).toBe(0)
    expect(upcastExtraDice({ level: 3 }, 5, 6)).toBe(0)
  })
})

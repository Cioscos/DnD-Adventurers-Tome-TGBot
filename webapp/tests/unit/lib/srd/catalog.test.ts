import { describe, it, expect } from 'vitest'
import {
  equipmentToForm, loadCatalog, loadSpellCatalog, localized, searchCatalog, spellCatalogKind, spellToForm, upcastBoth, upcastExtraDice, type SpellEntry,
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
      name: 'Palla di Fuoco', level: '3', casting_time: '1 azione', duration: 'Istantanea',
      damage_dice: '8d6', damage_type: 'fire', attack_save: 'SAVE', school: 'evocation',
      srd_index: 'fireball', higher_levels_dice: '1d6',
    })
    expect(f.range_area).toBe('45 m (sfera 6 m)')
    expect(f.components).toMatch(/^V, S, M \(/)
    expect(spellToForm(await find('fireball'), 'en', 'imperial').range_area).toBe('150 ft (sphere 20 ft)')
  })

  it('tolerates healing and no-attack spells; sleep prefills its pool dice', async () => {
    expect(spellToForm(await find('cure-wounds'), 'it', 'imperial')).toMatchObject({ damage_dice: '', damage_type: '', attack_save: '' })
    expect(spellToForm(await find('magic-missile'), 'it', 'imperial')).toMatchObject({ damage_dice: '3d4+3', attack_save: '' })
    const sleep = spellToForm(await find('sleep'), 'it', 'imperial')
    expect(sleep.damage_dice).toBe('5d8')
    expect(sleep.higher_levels_dice).toBe('2d8')  // 2014 pag. 279: la riserva cresce di 2d8 per slot oltre il 1°
  })

  it('upcastExtraDice mirrors the server rule', () => {
    const fb = { level: 3, higher_levels_dice: '1d6', srd_index: 'fireball' }
    expect(upcastExtraDice(fb, 5, 6)).toBe(2)
    expect(upcastExtraDice(fb, 3, 6)).toBe(0)
    expect(upcastExtraDice(fb, 5, 8)).toBe(0)
    // Sonno 2014 (pag. 279): +2d8 per slot anche sulle righe salvate senza dadi di scalata
    expect(upcastExtraDice({ level: 1, srd_index: 'sleep', higher_levels_dice: null }, 3, 8)).toBe(4)
    // Arma Spirituale: +1d8 ogni due slot nel 2014 (pag. 215), a ogni slot nel 2024 (pag. 319-320)
    expect(upcastExtraDice({ level: 2, srd_index: 'spiritual-weapon' }, 4, 8, '2014')).toBe(1)
    expect(upcastExtraDice({ level: 2, srd_index: 'spiritual-weapon', higher_levels_dice: '1d8' }, 4, 8, '2024')).toBe(2)
    // Raffica di Spine 2014 (pag. 266): al massimo 6d10
    expect(upcastExtraDice({ level: 1, srd_index: 'hail-of-thorns', higher_levels_dice: '1d10' }, 9, 10, '2014')).toBe(5)
    expect(upcastBoth('flame-strike', '2024')).toBe(true)
    expect(upcastBoth('jallarzis-storm-of-radiance', '2024')).toBe(true)
    expect(upcastBoth('flame-strike', '2014')).toBe(false)
    expect(upcastExtraDice({ level: 0, higher_levels_dice: '1d6' }, 5, 6)).toBe(0)
    expect(upcastExtraDice({ level: 3 }, 5, 6)).toBe(0)
    // Dardo incantato: un dardo (1d4+1) in più per livello, il bonus non conta come dado.
    expect(upcastExtraDice({ level: 1, higher_levels_dice: '1d4+1', srd_index: 'magic-missile' }, 3, 4)).toBe(2)
  })

  it('spell catalogue per edition', async () => {
    expect(spellCatalogKind('2014')).toBe('spells')
    expect(spellCatalogKind('2024')).toBe('spells-2024')
    const y24 = await loadCatalog('spells-2024')
    expect(y24.length).toBeGreaterThan(385)
    expect(y24.find((e) => e.index === 'hex')?.source).toBe('srd')
    expect((await loadCatalog('spells')).find((e) => e.index === 'hex')?.source).toBe('phb')
  })

  it('search also matches the old Italian name (aliases)', () => {
    const e = { index: 'acid-splash', name: { en: 'Acid Splash', it: 'Fiotto Acido' }, aliases: ['Spruzzo acido'] }
    expect(searchCatalog([e], 'spruzzo', 'it')).toEqual([e])
  })

  it('magic items read the edition catalogue, with the 2014 one for spells the 2024 lacks', async () => {
    const sp = await loadSpellCatalog('2024')
    expect(sp.find((e) => e.index === 'hex')?.source).toBe('srd')
    expect(sp.find((e) => e.index === 'branding-smite')).toBeDefined()
    expect(await loadSpellCatalog('2014')).toBe(await loadCatalog('spells'))
  })

  it('spellToForm carries the second part of the damage', async () => {
    const wave = (await loadCatalog('spells')).find((e) => e.index === 'destructive-wave') as SpellEntry
    expect(spellToForm(wave, 'it', 'metric')).toMatchObject({
      damage_dice: '5d6', damage_type: 'thunder', extra_damage_dice: '5d6', extra_damage_type: 'radiant|necrotic',
    })
  })

  it('equipmentToForm: la Rete non riceve un dado di danno, le altre armi restano uguali', async () => {
    const eq = await loadCatalog('equipment')
    const labels = { range: 'Gittata', thrown: 'Lancio' }
    const net = eq.find((e) => e.index === 'net')!
    expect(equipmentToForm(net, 'it', 'metric', labels).damage_dice).toBe('')
    const sword = eq.find((e) => e.index === 'longsword')!
    expect(equipmentToForm(sword, 'it', 'metric', labels).damage_dice).toBe('1d8')
  })
})

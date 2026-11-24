import { describe, expect, it } from 'vitest'
import { loadCatalog, spellToForm, upcastExtraDice, type SpellEntry } from '@/lib/srd/catalog'

const voce = async (index: string) => (await loadCatalog('spells')).find((e) => e.index === index) as SpellEntry

describe('caccia: regola 2014 incantesimi S-Z', () => {
  // caccia: {"id": "CB-3425", "fonte": "2014 · Incantesimi · Sfera Infuocata · pag. 277; Terremoto · pag. 285; Tempesta di Nevischio · pag. 284; Zona di Verità · pag. 289; Sembrare · pag. 275", "zona": "regola:2014/incantesimi-S-Z", "voce": "regola", "copre": ["carta:2014/spells.md#Sfera Infuocata", "carta:2014/spells.md#Terremoto", "carta:2014/spells.md#Tempesta di Nevischio", "carta:2014/spells.md#Zona di Verità", "carta:2014/spells.md#Sembrare"]}
  it.fails.each([
    ['flaming-sphere', 'dex'], ['earthquake', 'dex'], ['sleet-storm', 'dex'], ['zone-of-truth', 'cha'], ['seeming', 'cha'],
  ])('%s preso dal catalogo è un incantesimo con TS (%s)', async (index, caratteristica) => {
    const e = await voce(index)
    expect([e.attack_type, e.save_ability]).toEqual(['SAVE', caratteristica])
    expect(spellToForm(e, 'it', 'metric').attack_save).toBe('SAVE')
  })

  // caccia: {"id": "CB-3426", "fonte": "2014 · Incantesimi · Sonno · pag. 279", "zona": "regola:2014/incantesimi-S-Z", "voce": "limiti", "copre": ["carta:2014/spells.md#Sonno"]}
  it.fails('Sonno preso dal catalogo somma 2d8 alla riserva per ogni slot oltre il primo', async () => {
    const form = spellToForm(await voce('sleep'), 'it', 'metric')
    expect([form.damage_dice, form.higher_levels_dice]).toEqual(['5d8', '2d8'])
    expect(upcastExtraDice({ level: 1, srd_index: 'sleep', higher_levels_dice: '2d8' }, 3, 8)).toBe(4)
  })
})

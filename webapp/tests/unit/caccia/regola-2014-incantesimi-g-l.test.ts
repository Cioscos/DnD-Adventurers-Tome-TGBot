import { describe, expect, it } from 'vitest'
import { loadSpellCatalog, spellToForm, upcastExtraDice, type SpellEntry } from '@/lib/srd/catalog'

// La riga che il giocatore 2014 aggiunge dal catalogo, come la scrive il modulo.
const riga = async (index: string) => {
  const e = (await loadSpellCatalog('2014')).find((s) => s.index === index) as SpellEntry
  return spellToForm(e, 'it', 'metric')
}

describe('caccia: regola 2014 incantesimi G-L', () => {
  // caccia: {"id": "CB-3316", "fonte": "2014 · Incantesimi · Guardiani Spirituali · pag. 240; Glifo di Interdizione · pag. 239", "zona": "regola:2014/incantesimi-G-L", "voce": "regola", "copre": ["carta:2014/spells.md#Guardiani Spirituali", "carta:2014/spells.md#Glifo di Interdizione"]}
  it.fails.each([
    ['spirit-guardians', '3d8', '1d8'],
    ['glyph-of-warding', '5d8', '1d8'],
  ])('%s aggiunto dal catalogo 2014 ha i dadi di danno della carta', async (index, dadi, perSlot) => {
    const f = await riga(index)
    expect(f.damage_dice).toBe(dadi)
    expect(f.higher_levels_dice).toBe(perSlot)
  })

  // caccia: {"id": "CB-3317", "fonte": "2014 · Incantesimi · Lama Infuocata · pag. 247; Invocare il Fulmine · pag. 246; Guardiani Spirituali · pag. 240; Glifo di Interdizione · pag. 239; Levitazione · pag. 248; Individuazione dei Pensieri · pag. 244", "zona": "regola:2014/incantesimi-G-L", "voce": "regola", "copre": ["carta:2014/spells.md#Lama Infuocata", "carta:2014/spells.md#Invocare il Fulmine", "carta:2014/spells.md#Guardiani Spirituali", "carta:2014/spells.md#Glifo di Interdizione", "carta:2014/spells.md#Levitazione", "carta:2014/spells.md#Individuazione dei Pensieri"]}
  it.fails.each([
    ['flame-blade', 'ATK'],
    ['call-lightning', 'SAVE'],
    ['spirit-guardians', 'SAVE'],
    ['glyph-of-warding', 'SAVE'],
    ['levitate', 'SAVE'],
    ['detect-thoughts', 'SAVE'],
  ])('%s aggiunto dal catalogo 2014 dice se è un attacco o un tiro salvezza (%s)', async (index, tipo) => {
    expect((await riga(index)).attack_save).toBe(tipo)
  })

  // caccia: {"id": "CB-3318", "fonte": "2014 · Incantesimi · Lama Infuocata · pag. 247", "zona": "regola:2014/incantesimi-G-L", "voce": "limiti", "copre": ["carta:2014/spells.md#Lama Infuocata"]}
  it.fails.each([
    [3, 0], [4, 1], [5, 1], [6, 2], [8, 3], [9, 3],
  ])('Lama Infuocata 2014 allo slot %i annuncia %i d6 in più (uno ogni due livelli)', async (slot, inPiu) => {
    const f = await riga('flame-blade')
    expect(upcastExtraDice({ level: 2, srd_index: 'flame-blade', higher_levels_dice: f.higher_levels_dice }, slot, 6)).toBe(inPiu)
  })
})

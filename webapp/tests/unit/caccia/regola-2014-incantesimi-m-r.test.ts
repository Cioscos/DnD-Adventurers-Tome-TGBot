import { describe, expect, it } from 'vitest'
import { loadCatalog, spellToForm, upcastExtraDice, type SpellEntry } from '@/lib/srd/catalog'

const voce = async (index: string) => (await loadCatalog('spells')).find((e) => e.index === index) as SpellEntry

describe('caccia: regola 2014 incantesimi M-R', () => {
  // caccia: {"id": "CB-3372", "fonte": "2014 · Incantesimi · Raggio Rovente (tre raggi, ognuno un attacco a distanza) · pag. 267", "zona": "regola:2014/incantesimi-M-R", "voce": "regola", "copre": ["carta:2014/spells.md#Raggio Rovente"]}
  it('Raggio Rovente aggiunto dal catalogo è un incantesimo con tiro per colpire', async () => {
    const form = spellToForm(await voce('scorching-ray'), 'it', 'metric')
    expect(form.damage_dice).toBe('2d6')
    expect(form.attack_save).toBe('ATK')
  })

  // caccia: {"id": "CB-4872", "fonte": "decisione D-045 (tests/caccia/decisioni.md): lo slot oltre il 2° dà un raggio, non dadi in più; 2014 · Raggio Rovente · pag. 267; 2024 · pag. 313", "zona": "regola:2014/incantesimi-M-R", "voce": "regola", "copre": ["carta:2014/spells.md#Raggio Rovente", "carta:2024/spells.md#Raggio Rovente"]}
  it('Raggio Rovente con uno slot più alto non aggiunge dadi al danno di un raggio', () => {
    const riga = { level: 2, srd_index: 'scorching-ray', higher_levels_dice: '2d6' }
    expect(upcastExtraDice({ ...riga, rays: 3 }, 4, 6)).toBe(0)
    expect(upcastExtraDice({ ...riga, rays: null }, 4, 6)).toBe(4)
  })

  // caccia: {"id": "CB-3373", "fonte": "2014 · Incantesimi · Ragnatela, Muro di Pietra, Metamorfosi Pura, Parola del Potere Stordire, Muro Prismatico (tiro salvezza del bersaglio) · pag. 267, 254, 251, 258, 254", "zona": "regola:2014/incantesimi-M-R", "voce": "regola", "copre": ["carta:2014/spells.md#Ragnatela", "carta:2014/spells.md#Muro di Pietra", "carta:2014/spells.md#Metamorfosi Pura", "carta:2014/spells.md#Parola del Potere Stordire", "carta:2014/spells.md#Muro Prismatico"]}
  it.each(['web', 'wall-of-stone', 'true-polymorph', 'power-word-stun', 'prismatic-wall'])(
    '%s aggiunto dal catalogo chiede un tiro salvezza (mostra la CD)', async (index) => {
      expect(spellToForm(await voce(index), 'it', 'metric').attack_save).toBe('SAVE')
    })
})

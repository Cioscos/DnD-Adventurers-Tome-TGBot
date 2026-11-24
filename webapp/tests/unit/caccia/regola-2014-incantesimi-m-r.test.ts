import { describe, expect, it } from 'vitest'
import { loadCatalog, spellToForm, type SpellEntry } from '@/lib/srd/catalog'

const voce = async (index: string) => (await loadCatalog('spells')).find((e) => e.index === index) as SpellEntry

describe('caccia: regola 2014 incantesimi M-R', () => {
  // caccia: {"id": "CB-3372", "fonte": "2014 · Incantesimi · Raggio Rovente (tre raggi, ognuno un attacco a distanza) · pag. 267", "zona": "regola:2014/incantesimi-M-R", "voce": "regola", "copre": ["carta:2014/spells.md#Raggio Rovente"]}
  it.fails('Raggio Rovente aggiunto dal catalogo è un incantesimo con tiro per colpire', async () => {
    const form = spellToForm(await voce('scorching-ray'), 'it', 'metric')
    expect(form.damage_dice).toBe('2d6')
    expect(form.attack_save).toBe('ATK')
  })

  // caccia: {"id": "CB-3373", "fonte": "2014 · Incantesimi · Ragnatela, Muro di Pietra, Metamorfosi Pura, Parola del Potere Stordire, Muro Prismatico (tiro salvezza del bersaglio) · pag. 267, 254, 251, 258, 254", "zona": "regola:2014/incantesimi-M-R", "voce": "regola", "copre": ["carta:2014/spells.md#Ragnatela", "carta:2014/spells.md#Muro di Pietra", "carta:2014/spells.md#Metamorfosi Pura", "carta:2014/spells.md#Parola del Potere Stordire", "carta:2014/spells.md#Muro Prismatico"]}
  it.fails.each(['web', 'wall-of-stone', 'true-polymorph', 'power-word-stun', 'prismatic-wall'])(
    '%s aggiunto dal catalogo chiede un tiro salvezza (mostra la CD)', async (index) => {
      expect(spellToForm(await voce(index), 'it', 'metric').attack_save).toBe('SAVE')
    })
})

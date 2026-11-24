import { describe, expect, it } from 'vitest'
import { loadSpellCatalog, spellToForm, type SpellEntry } from '@/lib/srd/catalog'

// La riga che il giocatore 2024 aggiunge dal catalogo, come la scrive il modulo.
const riga = async (index: string) => {
  const e = (await loadSpellCatalog('2024')).find((s) => s.index === index) as SpellEntry
  return spellToForm(e, 'it', 'metric')
}

describe('caccia: regola 2024 incantesimi A-C', () => {
  // caccia: {"id": "CB-3670", "fonte": "2024 · Incantesimi · Colonna di fiamme · pag. 275", "zona": "regola:2024/incantesimi-A-C", "voce": "regola", "copre": ["carta:2024/spells.md#Colonna di fiamme"]}
  it.fails('Colonna di fiamme aggiunta dal catalogo 2024 ha anche i 5d6 radiosi', async () => {
    const f = await riga('flame-strike')
    expect([f.damage_dice, f.damage_type]).toEqual(['5d6', 'fire'])
    expect([f.extra_damage_dice, f.extra_damage_type]).toEqual(['5d6', 'radiant'])
  })

  // caccia: {"id": "CB-3671", "fonte": "2024 · Incantesimi · Contagio · pag. 256", "zona": "regola:2024/incantesimi-A-C", "voce": "regola", "copre": ["carta:2024/spells.md#Contagio"]}
  it('Contagio aggiunto dal catalogo 2024 ha le componenti V e S', async () => {
    expect((await riga('contagion')).components).toBe('V, S')
  })
})

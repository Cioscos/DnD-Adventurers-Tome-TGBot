import { describe, expect, it } from 'vitest'
import { loadSpellCatalog, spellToForm, type SpellEntry } from '@/lib/srd/catalog'

// La riga che il giocatore 2024 aggiunge dal catalogo, come la scrive il modulo.
const riga = async (index: string) => {
  const e = (await loadSpellCatalog('2024')).find((s) => s.index === index) as SpellEntry
  return spellToForm(e, 'it', 'metric')
}

describe('caccia: regola 2024 incantesimi S-Z', () => {
  // caccia: {"id": "CB-3872", "fonte": "2024 · Incantesimi · Trova Destriero · pag. 272; Velocità · pag. 284", "zona": "regola:2024/incantesimi-S-Z", "voce": "regola", "copre": ["carta:2024/spells.md#Trova destriero", "carta:2024/spells.md#Velocità"]}
  it.fails.each([
    ['find-steed', 'components', 'V, S'], // senza V il lancio non fa finire il nascondiglio
    ['haste', 'attack_save', ''], // Velocità non chiede TS: il bersaglio è consenziente
  ])('%s aggiunto dal catalogo 2024 ha %s come la carta', async (index, campo, atteso) => {
    const f = await riga(index)
    expect(f[campo as 'components' | 'attack_save']).toBe(atteso)
  })
})

import { describe, expect, it } from 'vitest'
import { featByKey, meetsPrerequisites } from '@/lib/feats'
import type { CharacterFull } from '@/types'

// Cavaliere Mistico scelto dal catalogo: la riga di classe non salva la caratteristica da incantatore
const cavaliereMistico = {
  id: 7, rules_edition: '2014', settings: { proficiencies_seeded: true }, total_level: 3,
  ability_scores: [], abilities: [], general_proficiencies: { armor: [], weapons: [], tools: [], other: [] },
  classes: [{ id: 1, class_name: 'fighter', level: 3, subclass: 'Cavaliere Mistico', subclass_key: 'eldritch_knight', spellcasting_ability: null }],
} as unknown as CharacterFull

describe('caccia: regola 2014 talenti', () => {
  // caccia: {"id": "CB-3027", "fonte": "2014 · Talenti · Incantatore da Guerra · pag. 168; Guerriero · Cavaliere Mistico · pag. 75", "zona": "regola:2014/talenti", "voce": "interazione", "copre": ["carta:2014/feats.md#Incantatore da Guerra / War Caster (pag. 168)", "route:/char/:id/abilities"]}
  it.fails('il Cavaliere Mistico vede Incantatore da Guerra fra i talenti che può prendere', () => {
    const talento = featByKey('war_caster')
    expect(talento).toBeTruthy()
    expect(meetsPrerequisites(talento!, cavaliereMistico, { manual: true })).toBe(true)
  })
})

import { describe, expect, it } from 'vitest'
import { featByKey, featsFor, meetsPrerequisites } from '@/lib/feats'
import type { CharacterFull } from '@/types'

const pg = (classe: string, livello: number, caratteristica: string | null) => ({
  id: 9, rules_edition: '2024', settings: { proficiencies_seeded: true }, total_level: livello, abilities: [],
  general_proficiencies: { armor: [], weapons: [], tools: [], other: [] },
  ability_scores: ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma'].map((name) => ({ name, value: 14 })),
  classes: [{ id: 1, class_name: classe, level: livello, spellcasting_ability: caratteristica }],
}) as unknown as CharacterFull

describe('caccia: regola 2024 talenti', () => {
  // caccia: {"id": "CB-3481", "fonte": "2024 · Talenti · Doni epici · pag. 210; Guerriero · Dono Epico · pag. 92", "zona": "regola:2024/talenti", "voce": "regola", "copre": ["carta:2024/feats.md#Robusto / Tough (pag. 202) - Origine", "carta:2024/classes/fighter.md#Dono Epico / Epic Boon (Guerriero 19, pag. 92)", "route:/char/:id"]}
  it.fails('la scelta del Dono Epico offre anche gli altri talenti per cui si è qualificati', () => {
    const chiavi = featsFor(pg('fighter', 19, null), '2024', 'boon', 'it').map((f) => f.key)
    expect(chiavi).toContain('2024_boon_fortitude')
    expect(chiavi).toContain('2024_tough')
  })

  // caccia: {"id": "CB-3482", "fonte": "2024 · Talenti · Dono del Richiamo degli incantesimi · pag. 211", "zona": "regola:2024/talenti", "voce": "limiti", "copre": ["carta:2024/feats.md#Dono del Richiamo degli incantesimi / Boon of Spell Recall (pag. 211) - Dono epico (livello 19+, privilegio Incantesimi)", "route:/char/:id/abilities"]}
  it.fails('il warlock con la sola Magia del Patto non soddisfa il Dono del Richiamo degli incantesimi', () => {
    const dono = featByKey('2024_boon_spell_recall')
    expect(dono).toBeTruthy()
    expect(meetsPrerequisites(dono!, pg('wizard', 19, 'intelligence'))).toBe(true)
    expect(meetsPrerequisites(dono!, pg('warlock', 19, 'charisma'))).toBe(false)
  })
})

import { describe, expect, it } from 'vitest'
import { featsFor } from '@/lib/feats'
import type { CharacterFull } from '@/types'

const cavaliere = {
  rules_edition: '2014', total_level: 4, abilities: [], settings: {},
  general_proficiencies: { armor: ['light', 'medium', 'heavy', 'shields'], weapons: [], tools: [], other: [] },
  ability_scores: ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']
    .map((name) => ({ name, value: 14 })),
  classes: [{ id: 1, class_name: 'fighter', level: 4, subclass: 'Cavaliere Mistico', subclass_key: 'eldritch_knight',
    spellcasting_ability: null, options: {} }],
} as unknown as CharacterFull

describe('caccia: regola 2014 guerriero', () => {
  // caccia: {"id": "CB-1775", "fonte": "2014 · Guerriero · Incantesimi del Cavaliere Mistico · pag. 75; Talenti · Incantatore da Guerra · pag. 168", "zona": "regola:2014/fighter", "voce": "interazione", "copre": ["carta:2014/classes/fighter.md#Incantesimi / Eldritch Knight Spellcasting (Cavaliere Mistico 3, pag. 75)"]}
  it.fails('il Cavaliere Mistico vede Incantatore da Guerra fra i talenti che può prendere', () => {
    const talento = featsFor(cavaliere, '2014', 'level', 'it').find((f) => f.key === 'war_caster')
    expect(talento).toBeDefined()
    expect(talento?.unmet).toBe(false)
  })
})

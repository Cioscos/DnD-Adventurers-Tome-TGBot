import { describe, expect, it } from 'vitest'
import { rollsDamageAgain } from '@/lib/spellType'
import type { Spell } from '@/types'

const riga = (srd_index: string, hit_damage: boolean): Spell => ({
  id: 1, name: srd_index, srd_index, level: 1, damage_dice: '1d6', is_concentration: true, effect: { target_kind: 'self', max_targets_by_slot: {}, choices: [], hit_damage },
}) as unknown as Spell

describe('caccia: revisione di lancio-core e dati-incantesimi-fe', () => {
  // caccia: {"id": "CB-4768", "fonte": "2014 · Incantesimi · Sortilegio · pag. 279; Manto del Crociato · pag. 250", "zona": "regola:2014/incantesimi-S-Z", "voce": "regola", "copre": ["carta:2014/spells.md#Sortilegio", "carta:2014/spells.md#Manto del Crociato", "route:/char/:id/spells"]}
  it('un incantesimo in concentrazione che dà i dadi agli attacchi non offre «tira i danni»', () => {
    expect(rollsDamageAgain(riga('hex', true))).toBe(false)
    expect(rollsDamageAgain(riga('crusaders-mantle', true))).toBe(false)
    // chi fa danni nei turni dopo sì, anche le punizioni che bruciano
    expect(rollsDamageAgain(riga('spirit-guardians', false))).toBe(true)
    expect(rollsDamageAgain(riga('searing-smite', true))).toBe(true)
    expect(rollsDamageAgain(riga('ensnaring-strike', true))).toBe(true)
  })
})

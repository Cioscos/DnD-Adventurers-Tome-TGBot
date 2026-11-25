import { describe, expect, it } from 'vitest'
import { ApiError } from '@/api/client'
import en from '@/locales/en.json'
import it_ from '@/locales/it.json'
import { serverErrorKey } from '@/lib/mutationError'
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

describe('caccia: revisione dei raggi', () => {
  // caccia: {"id": "CB-4853", "fonte": "invariante: ogni rifiuto del server ha un testo it/en (i raggi rimasti si perdono con un nuovo turno, D-037)", "zona": "regola:2024/incantesimi-D-F", "voce": "interazione", "copre": ["POST /characters/{char_id}/spells/{spell_id}/attack", "route:/char/:id/spells"]}
  it('il rifiuto di un raggio non più disponibile dice il motivo', () => {
    expect(serverErrorKey(new ApiError(409, { code: 'no_ray_left' }))).toBe('common.server_errors.no_ray_left')
    for (const testi of [it_, en]) expect((testi.common.server_errors as Record<string, string>).no_ray_left).toBeTruthy()
  })
})

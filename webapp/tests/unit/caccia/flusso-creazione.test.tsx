import { describe, expect, it } from 'vitest'
import { background24Payload, creationExtras, increasesValid, type Background2024Choice } from '@/lib/species'

describe('caccia: creazione', () => {
  // caccia: {"id": "CB-653", "fonte": "2024 · Background · pag. 177 (+2/+1 oppure +1/+1/+1 su tre caratteristiche)", "zona": "flusso:creazione", "voce": "limiti", "copre": ["route:/"]}
  it('gli aumenti del background validi sono solo +2/+1 e +1/+1/+1', () => {
    expect(increasesValid({ strength: 2, dexterity: 1 })).toBe(true)
    expect(increasesValid({ strength: 1, dexterity: 1, wisdom: 1 })).toBe(true)
    expect(increasesValid({ strength: 2, dexterity: 1, wisdom: 0 })).toBe(true)
    expect(increasesValid({ strength: 2, dexterity: 2 })).toBe(false)
    expect(increasesValid({ strength: 3 })).toBe(false)
    expect(increasesValid({ strength: 2 })).toBe(false)
    expect(increasesValid({ strength: 1, dexterity: 1 })).toBe(false)
    expect(increasesValid({ strength: 2, dexterity: 1, wisdom: 1 })).toBe(false)
    expect(increasesValid({})).toBe(false)
  })

  // caccia: {"id": "CB-654", "fonte": "invariante: il corpo inviato al server contiene solo ciò che il giocatore ha scelto", "zona": "flusso:creazione", "voce": "contratto", "copre": ["route:/"]}
  it('il corpo della creazione non manda aumenti a zero né punteggi se il passo è saltato', () => {
    const scelta = {
      entry: { key: 'soldier', tool: ['dice_set', 'chess_set'] }, increases: { strength: 2, dexterity: 1, wisdom: 0 }, tool: 'dice_set', equipment: 'gold',
    } as unknown as Background2024Choice
    expect(background24Payload(scelta)).toEqual({ key: 'soldier', increases: { strength: 2, dexterity: 1 }, tool: 'dice_set', equipment: 'gold' })
    expect(background24Payload({ ...scelta, tool: null })).not.toHaveProperty('tool')
    const punteggi = { strength: 15 }
    expect(creationExtras({ scores: punteggi, skipped: true, species: null, skills: [] })).toEqual({})
    expect(creationExtras({ scores: punteggi, skipped: false, species: null, skills: ['stealth', 'arcana'] }))
      .toEqual({ ability_scores: punteggi, skills: { stealth: true, arcana: true } })
  })
})

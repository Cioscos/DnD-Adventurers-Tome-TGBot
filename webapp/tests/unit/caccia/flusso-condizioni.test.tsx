import { afterEach, describe, expect, it, vi } from 'vitest'
import type { TFunction } from 'i18next'
import { formatCondition, refusedConditions } from '@/lib/conditions'
import { formatExpiry, formatSource } from '@/lib/conditionEffects'
import type { ConditionEffect } from '@/types'

afterEach(() => { vi.clearAllMocks() })

const t = ((k: string, o?: Record<string, unknown>) => (o ? `${k}|${JSON.stringify(o)}` : k)) as unknown as TFunction
const effetto = (extra: Partial<ConditionEffect>): ConditionEffect => ({
  slug: 'blinded', expiry_anchor: null, expiry_edge: null, expiry_count: null, save_ability: null, save_dc: null, save_edge: null,
  source_name: null, ends_with_concentration: false, applied_by_gm: false, source_note: null, ...extra,
} as ConditionEffect)

describe('caccia: pagina delle condizioni', () => {
  // caccia: {"id": "CB-561", "fonte": "invariante: l'avviso di immunità riguarda solo ciò che il tocco ha provato ad accendere", "zona": "flusso:condizioni", "voce": "normale", "copre": ["route:/char/:id/conditions"]}
  it('la mappa completa rimandata a ogni tocco segnala solo la condizione appena chiesta e rifiutata', () => {
    const richiesta = { blinded: true, prone: true, poisoned: false, exhaustion: 2 }
    expect(refusedConditions(richiesta, { blinded: true }, { blinded: true })).toEqual(['prone'])
    expect(refusedConditions(richiesta, { blinded: true, prone: true }, { blinded: true })).toEqual([])
  })

  // caccia: {"id": "CB-562", "fonte": "invariante: una durata di zero round non si mostra", "zona": "flusso:condizioni", "voce": "limiti", "copre": ["route:/char/:id/conditions"]}
  it('una scadenza a zero round o senza conteggio non produce testo', () => {
    expect(formatExpiry(effetto({ expiry_count: 0 }), t)).toBe('')
    expect(formatExpiry(effetto({ expiry_count: null }), t)).toBe('')
  })

  // caccia: {"id": "CB-563", "fonte": "invariante: la fonte dice la nota e la creatura quando ci sono entrambe", "zona": "flusso:condizioni", "voce": "normale", "copre": ["route:/char/:id/conditions"]}
  it('la fonte unisce nota e nome, o ne mostra uno solo', () => {
    expect(formatSource(effetto({ source_note: 'Ragnatela', source_name: 'Corvo' }))).toBe('Ragnatela (Corvo)')
    expect(formatSource(effetto({ source_name: 'Corvo' }))).toBe('Corvo')
    expect(formatSource(effetto({}))).toBeNull()
  })

  // caccia: {"id": "CB-564", "fonte": "2014 · Indebolimento · pag. 291 (livelli da 1 a 6)", "zona": "flusso:condizioni", "voce": "edizioni", "copre": ["route:/char/:id/conditions"]}
  it('lo sfinimento mostra il livello solo se positivo, e non altera le altre condizioni', () => {
    expect(formatCondition('exhaustion', 3, t, '2024')).toContain('"level":3')
    expect(formatCondition('exhaustion', 0, t, '2024')).toBe('character.conditions.exhaustion')
    expect(formatCondition('blinded', true, t)).toBe('character.conditions.blinded')
  })
})

import { afterEach, describe, expect, it, vi } from 'vitest'
import type { TFunction } from 'i18next'
import { formatCondition, refusedConditions } from '@/lib/conditions'
import { formatExpiry, formatSave, formatSource } from '@/lib/conditionEffects'
import itLocale from '@/locales/it.json'
import enLocale from '@/locales/en.json'
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

const CONDIZIONI = ['blinded', 'charmed', 'deafened', 'frightened', 'grappled', 'incapacitated', 'invisible', 'paralyzed', 'petrified',
  'poisoned', 'prone', 'restrained', 'stunned', 'unconscious']
const tChiave = ((k: string) => k) as unknown as TFunction
const trova = (loc: unknown, chiave: string): unknown => chiave.split('.').reduce<unknown>((o, p) => (o as Record<string, unknown> | undefined)?.[p], loc)

describe('caccia: testi della pagina delle condizioni', () => {
  // caccia: {"id": "CB-1299", "fonte": "invariante: ogni testo che la pagina può chiedere esiste in italiano e in inglese", "zona": "flusso:condizioni", "voce": "contratto", "copre": ["route:/char/:id/conditions"]}
  it('ogni scadenza e ogni TS ripetuto producono una chiave presente in entrambe le lingue', () => {
    const chiavi = new Set<string>()
    for (const anchor of ['owner', 'source'] as const) for (const edge of ['start', 'end'] as const) for (const n of [1, 2, 5]) {
      for (const nome of [undefined, 'Corvo']) chiavi.add(formatExpiry(effetto({ expiry_anchor: anchor, expiry_edge: edge, expiry_count: n }), tChiave, nome))
    }
    chiavi.add(formatExpiry(effetto({ expiry_count: 3 }), tChiave))
    chiavi.add(formatExpiry(effetto({ ends_with_concentration: true, source_name: 'Corvo' }), tChiave))
    for (const edge of ['start', 'end', null] as const) for (const nome of [undefined, 'Corvo']) {
      chiavi.add(formatSave(effetto({ save_ability: 'wisdom', save_dc: 13, save_edge: edge }), tChiave, nome) ?? '')
    }
    for (const lingua of [itLocale, enLocale]) for (const k of chiavi) {
      for (const parte of k.split(' · ')) expect(typeof (trova(lingua, parte) ?? trova(lingua, `${parte}_other`)), parte).toBe('string')  // i plurali stanno in _one/_other
    }
  })

  // caccia: {"id": "CB-1300", "fonte": "2014 · Indebolimento · pag. 291 (sei livelli); 2024 · Esaurimento · pag. 366", "zona": "flusso:condizioni", "voce": "edizioni", "copre": ["route:/char/:id/conditions"]}
  it('le descrizioni dei sei livelli di spossatezza e delle 14 condizioni esistono per ogni edizione e lingua', () => {
    for (const lingua of [itLocale, enLocale]) {
      const c = lingua.character.conditions as Record<string, unknown>
      const desc = c.desc as Record<string, unknown>
      for (const chiave of ['exhaustion_levels', 'exhaustion_levels_2024']) {
        expect(desc[chiave]).toHaveLength(6)
      }
      for (const chiave of ['exhaustion', 'exhaustion_2024']) expect(typeof desc[chiave]).toBe('string')
      for (const k of CONDIZIONI) {
        expect(typeof c[k], k).toBe('string')
        expect(typeof desc[k], k).toBe('string')
      }
      for (const chiave of ['exhaustion', 'exhaustion_2024', 'exhaustion_condition', 'exhaustion_condition_2024']) expect(typeof c[chiave]).toBe('string')
    }
  })

  // caccia: {"id": "CB-1301", "fonte": "invariante: «Azzera tutto» non deve mostrare avvisi di immunità per condizioni spente", "zona": "flusso:condizioni", "voce": "normale", "copre": ["route:/char/:id/conditions"]}
  it('azzerare tutto rimanda solo valori spenti e non segnala nulla come rifiutato', () => {
    const richiesta: Record<string, unknown> = { exhaustion: 0 }
    for (const k of CONDIZIONI) richiesta[k] = false
    expect(refusedConditions(richiesta, { exhaustion: 0 }, { blinded: true, exhaustion: 2 })).toEqual([])
  })

  // caccia: {"id": "CB-1302", "fonte": "invariante: nella vista del master il turno del portatore è nominato per nome", "zona": "flusso:condizioni", "voce": "limiti", "copre": ["route:/char/:id/conditions"]}
  it('con il nome del portatore la scadenza sul suo turno cita il nome e non dice «tuo»', () => {
    const testo = formatExpiry(effetto({ expiry_anchor: 'owner', expiry_edge: 'end', expiry_count: 2 }), t, 'Ilyra')
    expect(testo).toContain('Ilyra')
    expect(testo).not.toContain('_owner')
  })
})

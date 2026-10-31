import { describe, it, expect, beforeAll } from 'vitest'
import i18next from 'i18next'
import itLoc from '@/locales/it.json'
import enLoc from '@/locales/en.json'
import { formatExpiry, formatSave } from '@/lib/conditionEffects'
import type { ConditionEffect } from '@/types'

const eff = (o: Partial<ConditionEffect>): ConditionEffect => ({
  slug: 'poisoned', ends_with_concentration: false, applied_by_gm: false, ...o,
})

beforeAll(async () => {
  await i18next.init({
    lng: 'it', fallbackLng: 'it', interpolation: { escapeValue: false },
    resources: { it: { translation: itLoc }, en: { translation: enLoc } },
  })
})

describe('formatExpiry', () => {
  const t = i18next.t.bind(i18next)
  it('owner end next turn', () => {
    expect(formatExpiry(eff({ expiry_anchor: 'owner', expiry_edge: 'end', expiry_count: 1 }), t))
      .toBe('fino alla fine del tuo prossimo turno')
  })
  it('source start next turn names the source', () => {
    expect(formatExpiry(eff({ expiry_anchor: 'source', expiry_edge: 'start', expiry_count: 1, source_name: 'Orco' }), t))
      .toBe("fino all'inizio del prossimo turno di Orco")
  })
  it('count > 1 with anchor uses the ordinal phrasing', () => {
    expect(formatExpiry(eff({ expiry_anchor: 'owner', expiry_edge: 'end', expiry_count: 3 }), t))
      .toBe('fino alla fine del 3° tuo turno')
  })
  it('count only reads as rounds', () => {
    expect(formatExpiry(eff({ expiry_count: 3 }), t)).toBe('3 round')
  })
  it('concentration note needs a known source', () => {
    expect(formatExpiry(eff({ ends_with_concentration: true, source_name: 'Gandalf' }), t))
      .toBe('finché Gandalf è concentrato')
    expect(formatExpiry(eff({ ends_with_concentration: true }), t)).toBe('')
  })
  it('english plural', () => {
    expect(formatExpiry(eff({ expiry_count: 1 }), i18next.getFixedT('en'))).toBe('1 round')
    expect(formatExpiry(eff({ expiry_count: 2 }), i18next.getFixedT('en'))).toBe('2 rounds')
  })
})

describe('formatSave', () => {
  const t = i18next.t.bind(i18next)
  it('formats ability, dc and edge', () => {
    expect(formatSave(eff({ save_ability: 'constitution', save_dc: 13, save_edge: 'end' }), t))
      .toBe('TS COS CD 13 alla fine del tuo turno')
  })
  it('null without a save', () => {
    expect(formatSave(eff({}), t)).toBeNull()
  })
})

describe('vista GM (ownerName)', () => {
  const t = i18next.t.bind(i18next)
  it('il turno del portatore è in terza persona', () => {
    expect(formatExpiry(eff({ expiry_anchor: 'owner', expiry_edge: 'end', expiry_count: 1 }), t, 'Goblin'))
      .toBe('fino alla fine del prossimo turno di Goblin')
    expect(formatExpiry(eff({ expiry_anchor: 'source', expiry_edge: 'start', expiry_count: 1, source_name: 'Orco' }), t, 'Goblin'))
      .toBe("fino all'inizio del prossimo turno di Orco")
    expect(formatSave(eff({ save_ability: 'constitution', save_dc: 15, save_edge: 'end' }), t, 'Goblin'))
      .toBe('TS COS CD 15 alla fine del turno di Goblin')
  })
})

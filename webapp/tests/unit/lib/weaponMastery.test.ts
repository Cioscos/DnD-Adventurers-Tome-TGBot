import { describe, it, expect } from 'vitest'
import { masteryLabel } from '@/data/weaponMastery'
import itLocale from '@/locales/it.json'
import en from '@/locales/en.json'

const names = (l: typeof itLocale) => (l.character.inventory as unknown as { mastery_names: Record<string, string> }).mastery_names

describe('masteryLabel (point 32)', () => {
  it('translates the mastery key, whichever way the server or the table writes it', () => {
    const t = (k: string, o?: Record<string, unknown>) => names(itLocale)[k.split('.').pop()!] ?? String(o?.defaultValue)
    expect(masteryLabel(t, 'topple')).toBe('Atterrare')
    expect(masteryLabel(t, 'Slow')).toBe('Rallentare')
    expect(masteryLabel(t, 'unknown')).toBe('Unknown')
  })

  it('has every mastery of the table in both languages', () => {
    const keys = ['cleave', 'graze', 'nick', 'push', 'sap', 'slow', 'topple', 'vex']
    for (const l of [itLocale, en]) expect(Object.keys(names(l as typeof itLocale)).sort()).toEqual(keys)
  })
})

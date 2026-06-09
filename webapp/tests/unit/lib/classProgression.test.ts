import { describe, it, expect } from 'vitest'
import {
  progressionKey,
  progressionRows,
  localizeFeatures,
} from '@/lib/classProgression'
import progressionData from '@/data/class-progression.json'

describe('progressionKey — English class_name → Italian JSON key bridge', () => {
  it('maps the canonical English keys to the Italian title-case keys', () => {
    expect(progressionKey('wizard')).toBe('Mago')
    expect(progressionKey('barbarian')).toBe('Barbaro')
    expect(progressionKey('fighter')).toBe('Guerriero')
    expect(progressionKey('rogue')).toBe('Ladro')
  })

  it('falls back to the original string for custom/unknown classes', () => {
    expect(progressionKey('customclass')).toBe('customclass')
    expect(progressionKey('Mago')).toBe('Mago')
  })
})

describe('progressionRows', () => {
  it('returns 20 rows for a known class', () => {
    const rows = progressionRows('wizard')
    expect(rows).toBeDefined()
    expect(rows).toHaveLength(20)
  })

  it('returns undefined for an unknown class', () => {
    expect(progressionRows('nonexistent-class')).toBeUndefined()
  })

  // Contract: progressionRows must surface the SAME data the JSON holds under
  // the bridged key. A drift in either the bridge or the JSON breaks this.
  it('reads the bridged JSON rows (contract with class-progression.json)', () => {
    const data = progressionData as Record<
      string,
      { proficiency_bonus: number; spell_slots: number[] | null }[]
    >
    const rows = progressionRows('wizard')!
    expect(rows[0]).toEqual(data['Mago'][0])
    expect(rows[0].proficiency_bonus).toBe(2)
    expect(rows[0].spell_slots).toEqual([2, 0, 0, 0, 0, 0, 0, 0, 0])
  })
})

describe('localizeFeatures', () => {
  it('translates known feature tokens for Italian', () => {
    expect(localizeFeatures('Spellcasting', 'it')).toBe('Incantesimi')
    expect(localizeFeatures('Ability Score Improvement', 'it')).toBe(
      'Aumento dei Punteggi di Caratteristica',
    )
  })

  it('preserves a trailing "(qualifier)" suffix', () => {
    expect(localizeFeatures('Ability Score Improvement (2 usi)', 'it')).toBe(
      'Aumento dei Punteggi di Caratteristica (2 usi)',
    )
  })

  it('translates each comma-separated segment independently', () => {
    expect(localizeFeatures('Spellcasting, ASI', 'it')).toBe(
      'Incantesimi, Aumento Caratteristica',
    )
  })

  it('leaves unknown tokens untouched', () => {
    expect(localizeFeatures('Some Custom Feature', 'it')).toBe('Some Custom Feature')
  })

  it('returns the string unchanged for non-Italian locales', () => {
    expect(localizeFeatures('Spellcasting', 'en')).toBe('Spellcasting')
  })
})

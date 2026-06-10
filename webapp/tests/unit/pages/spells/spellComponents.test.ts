import { describe, it, expect } from 'vitest'
import { parseComponents, serializeComponents } from '@/pages/spells/spellComponents'

describe('parseComponents', () => {
  it('parses plain SRD combos', () => {
    expect(parseComponents('V, S, M')).toEqual({ tokens: ['V', 'S', 'M'], material: '', conformant: true })
    expect(parseComponents('V')).toEqual({ tokens: ['V'], material: '', conformant: true })
    expect(parseComponents('S, M')).toEqual({ tokens: ['S', 'M'], material: '', conformant: true })
  })

  it('extracts a trailing material detail in parentheses', () => {
    expect(parseComponents('V, S, M (un pizzico di sabbia)')).toEqual({
      tokens: ['V', 'S', 'M'],
      material: 'un pizzico di sabbia',
      conformant: true,
    })
  })

  it('normalizes case, spacing and token order', () => {
    expect(parseComponents(' m , v ')).toEqual({ tokens: ['V', 'M'], material: '', conformant: true })
  })

  it('treats the empty string as conformant (no components)', () => {
    expect(parseComponents('')).toEqual({ tokens: [], material: '', conformant: true })
  })

  it('flags unknown tokens as non-conformant but keeps the valid ones', () => {
    const parsed = parseComponents('V, XP, S')
    expect(parsed.tokens).toEqual(['V', 'S'])
    expect(parsed.conformant).toBe(false)
  })

  it('flags a material detail without the M token as non-conformant', () => {
    expect(parseComponents('V, S (incenso)').conformant).toBe(false)
  })
})

describe('serializeComponents', () => {
  it('serializes in canonical V, S, M order', () => {
    expect(serializeComponents(['M', 'V'], '')).toBe('V, M')
    expect(serializeComponents(['S', 'M', 'V'], '')).toBe('V, S, M')
  })

  it('appends the material detail only when M is selected', () => {
    expect(serializeComponents(['V', 'S', 'M'], 'una perla (100 mo)')).toBe('V, S, M (una perla (100 mo))')
    expect(serializeComponents(['V', 'S'], 'incenso')).toBe('V, S')
  })

  it('returns the empty string with no tokens', () => {
    expect(serializeComponents([], 'incenso')).toBe('')
  })

  it('round-trips SRD strings exactly', () => {
    for (const raw of ['V', 'S', 'M', 'V, S', 'V, M', 'S, M', 'V, S, M', 'V, S, M (un diamante da 300 mo)']) {
      const { tokens, material } = parseComponents(raw)
      expect(serializeComponents(tokens, material)).toBe(raw)
    }
  })
})

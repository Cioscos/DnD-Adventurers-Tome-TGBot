import { describe, it, expect } from 'vitest'
import { localizeDistances } from '@/lib/format'

describe('localizeDistances (U18)', () => {
  it('turns feet into meters in Italian', () => {
    expect(localizeDistances('120 ft', 'it')).toBe('36 m')
    expect(localizeDistances('60 ft.', 'it')).toBe('18 m')
    expect(localizeDistances('Self (15 feet cone)', 'it')).toBe('Self (4,5 m cone)')
    expect(localizeDistances('5 piedi', 'it')).toBe('1,5 m')
  })
  it('leaves English and metric text alone', () => {
    expect(localizeDistances('120 ft', 'en')).toBe('120 ft')
    expect(localizeDistances('9 m', 'it')).toBe('9 m')
    expect(localizeDistances('Contatto', 'it')).toBe('Contatto')
  })
})

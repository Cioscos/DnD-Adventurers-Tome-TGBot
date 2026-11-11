import { describe, it, expect } from 'vitest'
import { formatKm, formatMeters } from '@/store/unitSettings'

// Punto 43: raggi e portate degli stati arrivano in metri dal server e seguono l'impostazione delle unità.
describe('state distances follow the unit setting', () => {
  it('meters become feet on the table grid in imperial, stay meters in metric', () => {
    expect(formatMeters(9, 'imperial')).toBe('30 ft')
    expect(formatMeters(1.5, 'imperial')).toBe('5 ft')
    expect(formatMeters(18, 'imperial')).toBe('60 ft')
    expect(formatMeters(9, 'metric')).toBe('9 m')
    expect(formatMeters(1.5, 'metric')).toBe('1.5 m')
  })

  it('kilometers become miles in imperial, with the decimal separator of the language', () => {
    expect(formatKm(9, 'imperial')).toBe('6 mi')
    expect(formatKm(1.5, 'imperial')).toBe('1 mi')
    expect(formatKm(1.5, 'metric', 'en')).toBe('1.5 km')
    expect(formatKm(1.5, 'metric', 'it')).toBe('1,5 km')
  })
})

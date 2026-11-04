import { describe, expect, it } from 'vitest'
import { hpNumeralTone } from '@/lib/hpTone'

describe('hpNumeralTone', () => {
  it.each([
    [100, 'hp-glow-emerald'],
    [75, 'hp-glow-emerald'],
    [74, 'hp-glow-gold'],
    [26, 'hp-glow-gold'],
    [25, 'hp-glow-crimson'],
    [0, 'hp-glow-crimson'],
  ])('a %i%% usa %s', (pct, tone) => {
    expect(hpNumeralTone(pct)).toContain(tone)
  })
})

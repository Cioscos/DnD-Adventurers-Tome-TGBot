import { describe, it, expect } from 'vitest'
import { formatRounds } from '@/lib/spellDuration'

const t = (k: string, o?: Record<string, unknown>) => `${k}:${JSON.stringify(o)}`

describe('formatRounds', () => {
  it('keeps short durations in rounds', () => {
    expect(formatRounds(t, 10)).toBe('character.turn.state_rounds_total:{"n":10}')
  })
  it('reads 100 rounds as 10 minutes', () => {
    expect(formatRounds(t, 100)).toBe('character.turn.state_duration_minutes:{"count":10}')
  })
  it('reads 600 rounds as 1 hour and 14400 as 24 hours', () => {
    expect(formatRounds(t, 600)).toBe('character.turn.state_duration_hours:{"count":1}')
    expect(formatRounds(t, 14400)).toBe('character.turn.state_duration_hours:{"count":24}')
  })
})

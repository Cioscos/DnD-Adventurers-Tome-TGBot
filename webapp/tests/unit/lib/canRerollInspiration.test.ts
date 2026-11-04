import { describe, it, expect } from 'vitest'
import { canRerollInspiration } from '@/lib/rollOptions'

describe('canRerollInspiration', () => {
  it('is the 2024 rule: the 2014 inspiration is advantage taken before the roll', () => {
    expect(canRerollInspiration({ heroic_inspiration: true, rules_edition: '2024' })).toBe(true)
    expect(canRerollInspiration({ heroic_inspiration: true, rules_edition: '2014' })).toBe(false)
    expect(canRerollInspiration({ heroic_inspiration: false, rules_edition: '2024' })).toBe(false)
    expect(canRerollInspiration(undefined)).toBe(false)
  })
})

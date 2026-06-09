import { describe, it, expect } from 'vitest'
import { EVENT_META } from '@/lib/eventMeta'

describe('EVENT_META', () => {
  it('maps core history event types to an icon + tone', () => {
    for (const key of ['hp_change', 'rest', 'ac_change', 'level_change', 'death_save', 'dice_roll', 'concentration_save']) {
      expect(EVENT_META[key]).toBeDefined()
      expect(typeof EVENT_META[key].icon).toBe('function')
      expect(EVENT_META[key].tone).toContain('border')
    }
  })

  it('provides an "other" fallback entry', () => {
    expect(EVENT_META.other).toBeDefined()
    expect(typeof EVENT_META.other.icon).toBe('function')
  })
})

import { describe, it, expect } from 'vitest'
import type { Ability } from '@/types'
import { diffResourceMaxes } from '@/lib/resourceDiff'

// Minimal class-feature Ability; overrides tweak the fields under test.
function ability(over: Partial<Ability>): Ability {
  return {
    id: 1,
    name: 'Lay on Hands',
    is_passive: false,
    is_active: true,
    restoration_type: 'long_rest',
    is_class_feature: true,
    ...over,
  }
}

describe('diffResourceMaxes', () => {
  it('reports a positive max_uses delta for a class-feature ability', () => {
    const before = [ability({ id: 1, max_uses: 5 })]
    const after = [ability({ id: 1, max_uses: 10 })]
    expect(diffResourceMaxes(before, after)).toEqual([
      { abilityId: 1, name: 'Lay on Hands', prev: 5, next: 10 },
    ])
  })

  it('ignores non-class-feature abilities', () => {
    const before = [ability({ id: 1, max_uses: 1, is_class_feature: false })]
    const after = [ability({ id: 1, max_uses: 3, is_class_feature: false })]
    expect(diffResourceMaxes(before, after)).toEqual([])
  })

  it('ignores demotions (a class level-down is a deliberate edit)', () => {
    const before = [ability({ id: 1, max_uses: 10 })]
    const after = [ability({ id: 1, max_uses: 5 })]
    expect(diffResourceMaxes(before, after)).toEqual([])
  })

  it('ignores unchanged maxes', () => {
    const before = [ability({ id: 1, max_uses: 5 })]
    const after = [ability({ id: 1, max_uses: 5 })]
    expect(diffResourceMaxes(before, after)).toEqual([])
  })

  it('ignores an ability with a null/undefined max on either side', () => {
    const before = [ability({ id: 1, max_uses: undefined })]
    const after = [ability({ id: 1, max_uses: 5 })]
    expect(diffResourceMaxes(before, after)).toEqual([])
  })

  it('ignores abilities not present before (newly added)', () => {
    const before: Ability[] = []
    const after = [ability({ id: 7, max_uses: 4 })]
    expect(diffResourceMaxes(before, after)).toEqual([])
  })

  it('returns only the grown subset across a mixed list', () => {
    const before = [
      ability({ id: 1, name: 'Lay on Hands', max_uses: 5 }),
      ability({ id: 2, name: 'Channel Divinity', max_uses: 1 }),
    ]
    const after = [
      ability({ id: 1, name: 'Lay on Hands', max_uses: 10 }),
      ability({ id: 2, name: 'Channel Divinity', max_uses: 1 }), // unchanged
    ]
    expect(diffResourceMaxes(before, after)).toEqual([
      { abilityId: 1, name: 'Lay on Hands', prev: 5, next: 10 },
    ])
  })
})

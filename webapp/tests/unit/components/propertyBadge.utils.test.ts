import { describe, it, expect } from 'vitest'
import { tonePerValue } from '@/components/homebrew/propertyBadge.utils'
import type { Property } from '@/lib/homebrew/types'

function enumProp(over: Partial<Property> = {}): Property {
  return {
    key: 'state',
    type: 'enum',
    values: ['good', 'bad'],
    default: 'good',
    label_i18n: { it: 'Stato', en: 'State' },
    ...over,
  }
}

describe('tonePerValue with tone_by_value (#47)', () => {
  it('uses the author-declared tone over the heuristic, even for a non-state key', () => {
    const p = enumProp({ key: 'flavor', values: ['spicy', 'mild'], default: 'mild', tone_by_value: { spicy: 'danger', mild: 'success' } })
    expect(tonePerValue(p, 'spicy')).toBe('danger')
    expect(tonePerValue(p, 'mild')).toBe('success')
  })

  it('declared tone overrides a conflicting heuristic match', () => {
    // key is state-like and 'pessima' is a BAD token (heuristic → danger),
    // but the author marks it success → success wins.
    const p = enumProp({ key: 'quality', values: ['pessima', 'buona'], default: 'buona', tone_by_value: { pessima: 'success' } })
    expect(tonePerValue(p, 'pessima')).toBe('success')
  })

  it('falls back to the heuristic when the value has no declared tone', () => {
    const p = enumProp({ key: 'quality', values: ['pessima', 'buona'], default: 'buona', tone_by_value: { buona: 'success' } })
    expect(tonePerValue(p, 'pessima')).toBe('danger')
  })

  it('stays neutral for non-enum properties', () => {
    const p = enumProp({ type: 'number', values: undefined, default: 0 })
    expect(tonePerValue(p, 5)).toBe('neutral')
  })
})

import { describe, expect, it } from 'vitest'
import { ATLAS_COLORS, ATLAS_ICONS, BUILTIN_TYPES } from '@/lib/atlasIcons'

describe('atlasIcons', () => {
  it('every builtin type has its icon and colour', () => {
    for (const [, [icon, color]] of Object.entries(BUILTIN_TYPES)) {
      expect(ATLAS_ICONS[icon]).toBeDefined()
      expect(ATLAS_COLORS[color]).toBeDefined()
    }
  })
  it('has about 30 icons', () => {
    expect(Object.keys(ATLAS_ICONS).length).toBeGreaterThanOrEqual(28)
  })
})

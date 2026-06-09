import { describe, it, expect } from 'vitest'
import { GiCrossedSwords, GiCheckedShield, GiSwapBag } from 'react-icons/gi'
import { getItemTypeIcon } from '@/lib/itemIcons'

describe('getItemTypeIcon', () => {
  it('returns the specific icon for known item types', () => {
    expect(getItemTypeIcon('weapon')).toBe(GiCrossedSwords)
    expect(getItemTypeIcon('shield')).toBe(GiCheckedShield)
  })

  it('falls back to the generic bag for unknown, null or undefined types', () => {
    expect(getItemTypeIcon('zorblax')).toBe(GiSwapBag)
    expect(getItemTypeIcon(null)).toBe(GiSwapBag)
    expect(getItemTypeIcon(undefined)).toBe(GiSwapBag)
  })
})

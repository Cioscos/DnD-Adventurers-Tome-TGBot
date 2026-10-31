import { describe, it, expect } from 'vitest'
import { isConcentrating, concentrationLabel } from '@/lib/concentration'
import type { CharacterFull } from '@/types'

const c = (p: Record<string, unknown>) => p as unknown as CharacterFull

describe('concentration helper', () => {
  it('is false with neither a spell id nor an item spell', () => {
    expect(isConcentrating(c({ settings: {} }))).toBe(false)
    expect(concentrationLabel(c({ settings: {} }))).toBeUndefined()
  })
  it('reads the known spell name', () => {
    const ch = c({ concentrating_spell_id: 3, spells: [{ id: 3, name: 'Benedizione' }], settings: {} })
    expect(isConcentrating(ch)).toBe(true)
    expect(concentrationLabel(ch)).toBe('Benedizione')
  })
  it('reads an item spell from settings', () => {
    const ch = c({ settings: { concentration_item_spell: { item_id: 9, name: 'Volare' } } })
    expect(isConcentrating(ch)).toBe(true)
    expect(concentrationLabel(ch)).toBe('Volare')
  })
})

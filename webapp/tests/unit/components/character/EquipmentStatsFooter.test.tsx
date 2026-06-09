import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import EquipmentStatsFooter from '@/components/character/EquipmentStatsFooter'
import type { CharacterFull } from '@/types'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/store/unitSettings', () => ({
  useUnitSettings: (sel: (s: { system: string }) => unknown) => sel({ system: 'imperial' }),
  formatWeight: (v: number) => `${v} lb`,
  formatWeightValue: (v: number) => String(v),
  formatLength: (v: number) => `${v} ft`,
  weightUnitLabel: () => 'lb',
}))

const char = (over: Partial<CharacterFull> = {}): CharacterFull =>
  ({
    id: 1,
    ac: 15,
    ac_breakdown: { homebrew: 2 },
    speed: 30,
    speed_homebrew_modifier: 10,
    carry_capacity: 15,
    carry_capacity_override: null,
    ability_scores: [{ name: 'strength', value: 10 }],
    items: [
      { id: 1, name: 'Sword', item_type: 'weapon', is_equipped: true, equipment_slot: 'main_hand', weight: 3, quantity: 1, item_metadata: { damage_dice: '1d8' } },
      { id: 2, name: 'Plate', item_type: 'armor', is_equipped: true, weight: 13, quantity: 1 },
      { id: 3, name: 'Rations', item_type: 'generic', is_equipped: false, weight: 50, quantity: 1 },
    ],
    ...over,
  } as unknown as CharacterFull)

describe('EquipmentStatsFooter', () => {
  it('shows total AC as base AC plus the homebrew breakdown (15 + 2 = 17)', () => {
    render(<EquipmentStatsFooter char={char()} />)
    expect(screen.getByText('17')).toBeInTheDocument()
  })

  it('shows the main-hand weapon damage dice, and a dash when no weapon is equipped', () => {
    const { rerender } = render(<EquipmentStatsFooter char={char()} />)
    expect(screen.getByText('1d8')).toBeInTheDocument()
    rerender(<EquipmentStatsFooter char={char({ items: [] })} />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('sums only equipped item weight × quantity into encumbrance, against carry capacity', () => {
    // equipped: Sword 3 + Plate 13 = 16 (Rations 50 not equipped → excluded); cap 15 → overload.
    render(<EquipmentStatsFooter char={char()} />)
    expect(screen.getByText(/16\/15/)).toBeInTheDocument()
  })

  it('adds the homebrew speed modifier to base speed (30 + 10 = 40)', () => {
    render(<EquipmentStatsFooter char={char()} />)
    expect(screen.getByText('40 ft')).toBeInTheDocument()
  })
})

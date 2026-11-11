import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import RestResistancePicker from '@/components/character/RestResistancePicker'
import type { CharacterFull } from '@/types'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string, o?: Record<string, string>) => (o?.type ? `${k}:${o.type}` : k), i18n: { language: 'it' } }) }
})

const char = (types: string[] | null, current?: string) => ({
  id: 7,
  abilities: types ? [{ feature_key: 'warlock.fiendish_resilience', rest_damage_choices: types }] : [],
  active_states: current ? [{ key: 'fiendish_resilience', data: { damage_type: current } }] : [],
}) as unknown as CharacterFull

describe('RestResistancePicker', () => {
  it('offers the types the server lists and shows the current resistance', async () => {
    const onChange = vi.fn()
    renderWithProviders(<RestResistancePicker char={char(['fire', 'cold'], 'fire')} value="" onChange={onChange} />)
    expect(screen.getByText('character.quick_actions.rest_resistance_current:character.inventory.damage_types.dmg_fire')).toBeInTheDocument()
    expect(screen.queryByText('character.inventory.damage_types.dmg_force')).toBeNull()
    await userEvent.click(screen.getByText('character.inventory.damage_types.dmg_cold'))
    expect(onChange).toHaveBeenCalledWith('cold')
  })

  it('taps the chosen type again to go back to keeping the current one', async () => {
    const onChange = vi.fn()
    renderWithProviders(<RestResistancePicker char={char(['fire', 'cold'])} value="cold" onChange={onChange} />)
    await userEvent.click(screen.getByText('character.inventory.damage_types.dmg_cold'))
    expect(onChange).toHaveBeenCalledWith('')
  })

  it('shows nothing for a character without the feature', () => {
    renderWithProviders(<RestResistancePicker char={char(null)} value="" onChange={() => {}} />)
    expect(screen.queryByTestId('rest-resistance')).toBeNull()
  })
})

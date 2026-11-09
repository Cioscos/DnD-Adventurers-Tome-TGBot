import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import RestAllyTempPicker from '@/components/character/RestAllyTempPicker'
import type { CharacterFull } from '@/types'

const { sessionAllies } = vi.hoisted(() => ({ sessionAllies: vi.fn() }))
vi.mock('@/api/client', () => ({ api: { characters: { sessionAllies } } }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

const char = (cunning: Record<string, unknown> | null) => ({ id: 7, abilities: cunning ? [{ feature_key: 'warlock.magical_cunning', ...cunning }] : [] }) as unknown as CharacterFull

describe('RestAllyTempPicker', () => {
  it('lists the table and caps the choice at ally_max', async () => {
    sessionAllies.mockResolvedValue([{ id: 31, name: 'Brun' }, { id: 32, name: 'Lia' }])
    const onChange = vi.fn()
    renderWithProviders(<RestAllyTempPicker char={char({ gives_to_ally: true, ally_max: 1 })} value={[31]} onChange={onChange} />)
    await userEvent.click(await screen.findByRole('switch', { name: 'Lia' }))
    expect(onChange).not.toHaveBeenCalledWith([31, 32])  // already at the cap
    await userEvent.click(screen.getByRole('switch', { name: 'Brun' }))
    expect(onChange).toHaveBeenCalledWith([])
  })

  it('does not offer a dead creature (the server would refuse the rest)', async () => {
    sessionAllies.mockResolvedValue([{ id: 31, name: 'Brun', dead: true }, { id: 32, name: 'Lia', dead: false }])
    renderWithProviders(<RestAllyTempPicker char={char({ gives_to_ally: true, ally_max: 2 })} value={[]} onChange={() => {}} />)
    expect(await screen.findByRole('switch', { name: 'Lia' })).toBeInTheDocument()
    expect(screen.queryByRole('switch', { name: 'Brun' })).toBeNull()
  })

  it('shows nothing for a warlock that is not Celestial (Magical Cunning gives nothing to allies)', () => {
    renderWithProviders(<RestAllyTempPicker char={char({ gives_to_ally: false })} value={[]} onChange={() => {}} />)
    expect(screen.queryByTestId('rest-ally-temp')).toBeNull()
  })
})

import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../../utils/renderWithProviders'
import ActiveStatesBar from '@/components/rules/ActiveStatesBar'
import type { CharacterFull } from '@/types'

vi.mock('@/api/client', () => ({ api: { characters: { endActiveState: vi.fn() } } }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

const rage = { key: 'rage', feature_key: 'barbarian.rage', rounds_left: 4, ends_on: ['manual'], name: 'Ira' }
const char = (states: unknown[], abilities: unknown[]) => ({ id: 7, active_states: states, abilities } as unknown as CharacterFull)

describe('ActiveStatesBar', () => {
  it('lists under a state the features that act on others, with their text', () => {
    renderWithProviders(<ActiveStatesBar char={char(
      [{ ...rage, data: { others: ['barbarian.totem_wolf', 'barbarian.gone'] } }],
      [{ id: 1, name: 'Ira', feature_key: 'barbarian.rage' },
        { id: 2, name: 'Lupo (Spirito Totemico)', feature_key: 'barbarian.totem_wolf', description: 'Gli alleati hanno vantaggio.' }],
    )} />)
    expect(screen.getByText('Lupo (Spirito Totemico): Gli alleati hanno vantaggio.')).toBeInTheDocument()
  })

  it('shows nothing extra for a state without effects on others', () => {
    renderWithProviders(<ActiveStatesBar char={char([{ ...rage, data: {} }], [{ id: 1, name: 'Ira', feature_key: 'barbarian.rage' }])} />)
    expect(screen.getByText('Ira')).toBeInTheDocument()
    expect(screen.queryByText(/:/)).not.toBeInTheDocument()
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import UndyingSentinelOffer from '@/components/character/UndyingSentinelOffer'
import type { CharacterFull } from '@/types'

const featureUse = vi.fn()
vi.mock('@/api/client', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, api: { characters: { featureUse: (...args: unknown[]) => featureUse(...args) } } }
})
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }))

const base = {
  id: 7, is_dead: false, current_hit_points: 0,
  abilities: [{ id: 1, feature_key: 'paladin.undying_sentinel', max_uses: 1, uses: 1 }],
}
const char = (over: Record<string, unknown> = {}) => ({ ...base, ...over }) as unknown as CharacterFull

describe('UndyingSentinelOffer', () => {
  beforeEach(() => { featureUse.mockReset(); featureUse.mockResolvedValue({}) })

  it('offers to stay at 1 HP at 0 HP and uses the feature on tap', async () => {
    renderWithProviders(<UndyingSentinelOffer charId={7} char={char()} />)
    await userEvent.click(screen.getByText('Resta a 1 PF'))
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'paladin.undying_sentinel'))
  })

  it.each([
    ['the character stands', { current_hit_points: 5 }],
    ['the use is spent', { abilities: [{ id: 1, feature_key: 'paladin.undying_sentinel', max_uses: 1, uses: 0 }] }],
    ['the character is dead', { is_dead: true }],
    ['the feature is missing', { abilities: [] }],
  ])('shows nothing when %s', (_name, over) => {
    renderWithProviders(<UndyingSentinelOffer charId={7} char={char(over)} />)
    expect(screen.queryByText('Resta a 1 PF')).toBeNull()
  })
})

import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../utils/renderWithProviders'
import DiceStats from '@/pages/DiceStats'

const { stats } = vi.hoisted(() => ({ stats: vi.fn() }))

vi.mock('@/api/client', () => ({ api: { dice: { stats, resetStats: vi.fn() } } }))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '7' }) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/ConfirmSheet', () => ({ default: () => null }))

afterEach(() => { stats.mockReset() })

describe('DiceStats', () => {
  it('shows the empty state when there really are no rolls', async () => {
    stats.mockResolvedValue({ stats: {} })
    renderWithProviders(<DiceStats />)
    expect(await screen.findByText('character.dice_stats.empty_title')).toBeInTheDocument()
  })

  it('failed fetch without cache shows offline unavailable, not empty', async () => {
    stats.mockRejectedValue(new TypeError('Failed to fetch'))
    renderWithProviders(<DiceStats />)
    expect(await screen.findByText('common.offline_unavailable')).toBeInTheDocument()
    expect(screen.queryByText('character.dice_stats.empty_title')).not.toBeInTheDocument()
  })
})

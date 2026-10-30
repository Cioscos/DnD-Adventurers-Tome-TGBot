import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import SessionRoom from '@/pages/SessionRoom'
import { ApiError } from '@/api/client'

const { live, me } = vi.hoisted(() => ({ live: vi.fn(), me: vi.fn() }))

vi.mock('@/api/client', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, api: { me, sessions: { live }, share: { invite: vi.fn() } } }
})
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '12' }), useNavigate: () => vi.fn() }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({
  haptic: new Proxy({}, { get: () => () => {} }),
  canShareMessage: () => false,
  telegramConfirm: vi.fn(),
}))
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})

afterEach(() => { live.mockReset(); me.mockReset() })

describe('SessionRoom without data', () => {
  it('does not call a network error "not found", and offers a retry', async () => {
    me.mockResolvedValue({ user_id: 1 })
    live.mockRejectedValue(new TypeError('Failed to fetch'))
    renderWithProviders(<SessionRoom />)
    expect(await screen.findByText('common.offline_unavailable')).toBeTruthy()
    expect(screen.queryByText('session.not_found')).toBeNull()

    await userEvent.click(screen.getByRole('button', { name: 'common.retry' }))
    await waitFor(() => expect(live).toHaveBeenCalledTimes(2))
  })

  it('does not call a server error "not found"', async () => {
    me.mockResolvedValue({ user_id: 1 })
    live.mockRejectedValue(new ApiError(500, 'boom'))
    renderWithProviders(<SessionRoom />)
    expect(await screen.findByText('common.offline_unavailable')).toBeTruthy()
    expect(screen.queryByText('session.not_found')).toBeNull()
  })

  it.each([404, 403])('says not found on a %i', async (status) => {
    me.mockResolvedValue({ user_id: 1 })
    live.mockRejectedValue(new ApiError(status, 'nope'))
    renderWithProviders(<SessionRoom />)
    expect(await screen.findByText('session.not_found')).toBeTruthy()
    expect(screen.queryByText('common.offline_unavailable')).toBeNull()
  })
})

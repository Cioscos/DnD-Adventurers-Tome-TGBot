import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Combat from '@/pages/Combat'
import type { EncounterLive, GameSessionLive } from '@/types'

const { navigateSpy, toastInfo, liveState } = vi.hoisted(() => ({
  navigateSpy: vi.fn(),
  toastInfo: vi.fn(),
  liveState: { data: undefined as unknown },
}))

vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '12' }), useNavigate: () => navigateSpy }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('sonner', () => ({ toast: { info: toastInfo, success: vi.fn(), error: vi.fn() } }))
vi.mock('@/api/client', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, api: { me: () => Promise.resolve({ user_id: 99 }) } }
})
vi.mock('@/hooks/useSessionLive', () => ({
  useSessionLive: () => ({ data: liveState.data, isLoading: false, isError: false, error: null, refetch: vi.fn() }),
}))
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/pages/session/CombatPanel', () => ({ default: () => <div data-testid="combat-panel" /> }))

const enc: EncounterLive = {
  id: 1, mode: 'full', status: 'active', round: 1, active_combatant_id: null,
  created_at: '', started_at: null, ended_at: null, combatants: [],
}
const live = (e: EncounterLive | null): GameSessionLive => ({
  id: 12, code: 'ABC123', gm_user_id: 1, gm_display_name: 'GM', status: 'active', title: null,
  created_at: '', closed_at: null, participants: [], live_characters: [], encounter: e,
})

const qc = new QueryClient()
const ui = () => <QueryClientProvider client={qc}><Combat /></QueryClientProvider>

beforeEach(() => { navigateSpy.mockReset(); toastInfo.mockReset() })

describe('Combat page', () => {
  it('redirects to the session when there is no open encounter', () => {
    liveState.data = live(null)
    render(ui())
    expect(navigateSpy).toHaveBeenCalledWith('/session/12', { replace: true })
    expect(toastInfo).not.toHaveBeenCalled()
  })

  it('redirects with a toast when the encounter disappears between polls', () => {
    liveState.data = live(enc)
    const { rerender } = render(ui())
    expect(screen.getByTestId('combat-panel')).toBeInTheDocument()
    expect(navigateSpy).not.toHaveBeenCalled()
    liveState.data = live(null)
    rerender(ui())
    expect(toastInfo).toHaveBeenCalledWith('session.combat.ended_toast')
    expect(navigateSpy).toHaveBeenCalledWith('/session/12', { replace: true })
  })

  it('redirects when the session is closed', () => {
    liveState.data = { ...live(enc), status: 'closed' }
    render(ui())
    expect(navigateSpy).toHaveBeenCalledWith('/session/12', { replace: true })
  })
})

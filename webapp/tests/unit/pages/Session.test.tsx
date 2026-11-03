import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Session from '@/pages/Session'

const { me, list, create, navigateSpy, campaignList } = vi.hoisted(() => ({ me: vi.fn(), list: vi.fn(), create: vi.fn(), navigateSpy: vi.fn(), campaignList: vi.fn() }))

vi.mock('@/api/client', () => ({ api: { sessions: { me, create }, characters: { list }, campaigns: { list: campaignList, create: vi.fn() } } }))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useNavigate: () => navigateSpy }
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
vi.mock('@/components/ui/Surface', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/FancyHeader', async () => {
  const React = await import('react')
  return { default: (p: { title?: unknown }) => React.createElement('div', null, p.title) }
})
vi.mock('@/components/ui/Reveal', async () => {
  const React = await import('react')
  return { default: { Stagger: (p: { children?: unknown }) => React.createElement('div', null, p.children), Item: (p: { children?: unknown }) => React.createElement('div', null, p.children) } }
})
vi.mock('@/components/ui/Skeleton', async () => {
  const React = await import('react')
  const S = () => React.createElement('div', { 'data-testid': 'skeleton' })
  return { default: { Line: S, Rect: S, Circle: S } }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void; disabled?: boolean; loading?: boolean; children?: unknown }) => React.createElement('button', { onClick: p.onClick, disabled: p.disabled || p.loading }, p.children) }
})

vi.mock('@/components/ui/Sheet', () => ({
  default: ({ open, title, children }: { open: boolean; title?: string; children: React.ReactNode }) => (open ? <div><h2>{title}</h2>{children}</div> : null),
}))

afterEach(() => { campaignList.mockReset(); me.mockReset(); list.mockReset(); create.mockReset(); navigateSpy.mockReset() })

describe('Session', () => {
  it('resumes an active session', async () => {
    me.mockResolvedValue({ id: 5, code: 'ABCDEF', gm_user_id: 1, title: 'La Cripta', participants: [{ role: 'game_master', user_id: 1 }] })
    list.mockResolvedValue([])
    renderWithProviders(<Session />)
    await userEvent.click(await screen.findByRole('button', { name: 'session.resume' }))
    expect(navigateSpy).toHaveBeenCalledWith('/session/5')
  })

  it('offers create + join on the landing when there is no active session', async () => {
    me.mockResolvedValue(null)
    list.mockResolvedValue([{ id: 7, name: 'Aragorn', class_summary: 'Ranger' }])
    campaignList.mockResolvedValue([])
    create.mockResolvedValue({ id: 9 })
    renderWithProviders(<Session />)
    const createBtn = await screen.findByRole('button', { name: 'session.create_button' })
    expect(screen.getByRole('button', { name: 'session.join_button' })).toBeEnabled()
    await userEvent.click(createBtn)
    expect(await screen.findByText('campaign.start_title')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'campaign.start_go' }))
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
  })

  it('lists "my campaigns" with links to the campaign page', async () => {
    me.mockResolvedValue(null)
    list.mockResolvedValue([])
    campaignList.mockResolvedValue([
      { id: 3, name: 'Coda del Vento', is_gm: true, member_count: 4, last_session_at: null, active_session_id: null },
      { id: 4, name: 'Phandalin', is_gm: false, member_count: 3, last_session_at: null, active_session_id: null },
    ])
    renderWithProviders(<Session />)
    expect(await screen.findByText('campaign.mine')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Phandalin/ }))
    expect(navigateSpy).toHaveBeenCalledWith('/campaign/4')
  })

  it('keeps "my campaigns" reachable while a session is active', async () => {
    me.mockResolvedValue({ id: 5, code: 'ABCDEF', gm_user_id: 1, title: 'La Cripta', participants: [{ role: 'game_master', user_id: 1 }] })
    list.mockResolvedValue([])
    campaignList.mockResolvedValue([
      { id: 3, name: 'Coda del Vento', is_gm: true, member_count: 4, last_session_at: null, active_session_id: 5 },
    ])
    renderWithProviders(<Session />)
    expect(await screen.findByRole('button', { name: 'session.resume' })).toBeInTheDocument()
    await userEvent.click(await screen.findByRole('button', { name: /Coda del Vento/ }))
    expect(navigateSpy).toHaveBeenCalledWith('/campaign/3')
  })

  it('disables join when the player has no characters', async () => {
    me.mockResolvedValue(null)
    list.mockResolvedValue([])
    renderWithProviders(<Session />)
    expect(await screen.findByRole('button', { name: 'session.join_button' })).toBeDisabled()
  })

  it('failed character fetch offers a retry instead of claiming there are no characters', async () => {
    me.mockResolvedValue(null)
    list.mockRejectedValue(new TypeError('Failed to fetch'))
    renderWithProviders(<Session />)
    expect(await screen.findByText('common.offline_unavailable')).toBeInTheDocument()
    expect(screen.queryByText('session.no_characters_hint')).not.toBeInTheDocument()
    list.mockResolvedValue([{ id: 1, name: 'Aragorn' }])
    await userEvent.click(screen.getByRole('button', { name: 'common.retry' }))
    expect(await screen.findByRole('button', { name: 'session.join_button' })).toBeEnabled()
  })
})

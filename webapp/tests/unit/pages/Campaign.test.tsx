import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '../utils/renderWithProviders'
import Campaign from '@/pages/Campaign'
import type { CampaignDetail } from '@/types'

const { get, setStatus, removeMember, regen, remove, createSession, share, navigateSpy } = vi.hoisted(() => ({
  get: vi.fn(), setStatus: vi.fn(), removeMember: vi.fn(), regen: vi.fn(), remove: vi.fn(),
  createSession: vi.fn(), share: vi.fn(), navigateSpy: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: {
    campaigns: { get, setMemberStatus: setStatus, removeMember, regenerateCode: regen, remove },
    sessions: { create: createSession },
    share: { campaignInvite: share },
  },
  ApiError: class ApiError extends Error {},
}))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useNavigate: () => navigateSpy }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({
  haptic: new Proxy({}, { get: () => () => {} }),
  canShareMessage: () => true,
  shareTelegramMessage: vi.fn(),
}))
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/Sheet', () => ({
  default: ({ open, children }: { open: boolean; children: React.ReactNode }) => (open ? <div>{children}</div> : null),
}))

const detail = (over: Partial<CampaignDetail> = {}): CampaignDetail => ({
  id: 5, name: 'La Coda del Vento', invite_code: 'WIND4242', is_gm: true, gm_user_id: 1, active_session_id: null,
  members: [
    { character_id: 10, character_name: 'Thorin', class_summary: 'Guerriero 5', total_level: 5, user_id: 2, player_name: 'Aldo', status: 'active', is_mine: false },
    { character_id: 11, character_name: 'Grom', class_summary: 'Barbaro 5', total_level: 5, user_id: 3, player_name: 'Carlo', status: 'dead', is_mine: false },
  ],
  stash: {
    items: [{ id: 1, name: 'Carro', weight: 0, quantity: 1, item_type: 'container', is_equipped: false, item_metadata: { container: { capacity_lb: null, counts_weight: false, quick_access: false } } }],
    currency: { id: 1, copper: 0, silver: 85, electrum: 0, gold: 12400, platinum: 0 },
  },
  sessions: [{ id: 8, created_at: '2026-10-28T20:00:00+00:00', duration_seconds: 13200 }, { id: 9, created_at: '2026-10-21T20:00:00+00:00', duration_seconds: 14700 }, { id: 10, created_at: '2026-10-14T20:00:00+00:00', duration_seconds: 18000 }],
  my_last_character_id: null,
  ...over,
} as CampaignDetail)

const renderPage = () => renderWithProviders(
  <Routes><Route path="/campaign/:id" element={<Campaign />} /></Routes>, { route: '/campaign/5' },
)

beforeEach(() => {
  Object.defineProperty(navigator, 'clipboard', { value: { writeText: vi.fn().mockResolvedValue(undefined) }, configurable: true })
})
afterEach(() => { vi.clearAllMocks() })

describe('Campaign page', () => {
  it('shows the GM view: code, members, stash, sessions with formatted duration', async () => {
    get.mockResolvedValue(detail())
    renderPage()
    expect(await screen.findByText('La Coda del Vento')).toBeInTheDocument()
    expect(screen.getByText('WIND4242')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'common.copy' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'share.action' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'campaign.regenerate' })).toBeInTheDocument()
    expect(screen.getByText('Thorin')).toBeInTheDocument()
    expect(screen.getByText('Grom')).toBeInTheDocument()
    expect(screen.getByText(/12\.400/)).toBeInTheDocument()
    expect(screen.getByText(/Carro/)).toBeInTheDocument()
    expect(screen.getByText(/3h 40m/)).toBeInTheDocument()
    expect(screen.getByText('4h 05m')).toBeInTheDocument()
    expect(screen.getByText('5h')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'campaign.delete' })).toBeInTheDocument()
  })

  it('starts the session in this campaign', async () => {
    get.mockResolvedValue(detail())
    createSession.mockResolvedValue({ id: 77 })
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'campaign.start_session' }))
    await waitFor(() => expect(createSession).toHaveBeenCalledWith(undefined, 5))
    await waitFor(() => expect(navigateSpy).toHaveBeenCalledWith('/session/77'))
  })

  it('with an active session hides the start button and offers to go there', async () => {
    get.mockResolvedValue(detail({ active_session_id: 31 }))
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'campaign.go_to_session' }))
    expect(screen.queryByRole('button', { name: 'campaign.start_session' })).not.toBeInTheDocument()
    expect(navigateSpy).toHaveBeenCalledWith('/session/31')
  })

  it('GM changes a member status and removes a member after confirmation', async () => {
    get.mockResolvedValue(detail())
    setStatus.mockResolvedValue(detail())
    removeMember.mockResolvedValue(undefined)
    renderPage()
    await screen.findByText('Thorin')
    await userEvent.click(screen.getAllByRole('button', { name: 'campaign.status_reserve' })[0])
    await waitFor(() => expect(setStatus).toHaveBeenCalledWith(5, 10, 'reserve'))
    await userEvent.click(screen.getAllByRole('button', { name: 'campaign.remove_member' })[0])
    expect(removeMember).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'campaign.remove_member_confirm' }))
    await waitFor(() => expect(removeMember).toHaveBeenCalledWith(5, 10))
  })

  it('regenerates the code and deletes the campaign only after confirmation', async () => {
    get.mockResolvedValue(detail())
    regen.mockResolvedValue({ invite_code: 'NEWCODE1' })
    remove.mockResolvedValue(undefined)
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'campaign.regenerate' }))
    await userEvent.click(screen.getByRole('button', { name: 'campaign.regenerate_confirm' }))
    await waitFor(() => expect(regen).toHaveBeenCalledWith(5))
    await userEvent.click(screen.getByRole('button', { name: 'campaign.delete' }))
    expect(remove).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'campaign.delete_confirm' }))
    await waitFor(() => expect(remove).toHaveBeenCalledWith(5))
    expect(navigateSpy).toHaveBeenCalledWith('/session', { replace: true })
  })

  it('player view: no code or GM actions, can manage only own PG', async () => {
    get.mockResolvedValue(detail({
      is_gm: false, invite_code: null,
      members: [
        { character_id: 10, character_name: 'Thorin', class_summary: 'Guerriero 5', total_level: 5, user_id: 2, player_name: 'Aldo', status: 'active', is_mine: true },
        { character_id: 12, character_name: 'Lyra', class_summary: 'Maga 5', total_level: 5, user_id: 4, player_name: 'Bea', status: 'active', is_mine: false },
      ],
    }))
    renderPage()
    await screen.findByText('Thorin')
    expect(screen.queryByText('WIND4242')).not.toBeInTheDocument()
    for (const k of ['campaign.start_session', 'campaign.regenerate', 'campaign.delete', 'share.action'])
      expect(screen.queryByRole('button', { name: k })).not.toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'campaign.status_reserve' })).toHaveLength(1)
    expect(screen.getAllByRole('button', { name: 'campaign.remove_member' })).toHaveLength(1)
    expect(within(screen.getByTestId('members')).getByText('Lyra')).toBeInTheDocument()
  })

  it('a generic load error offers a retry', async () => {
    get.mockRejectedValueOnce(new Error('offline')).mockResolvedValue(detail())
    renderPage()
    expect(await screen.findByText('campaign.load_error')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'common.retry' }))
    expect(await screen.findByText('Thorin')).toBeInTheDocument()
  })
})

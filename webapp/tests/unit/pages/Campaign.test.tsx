import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '../utils/renderWithProviders'
import Campaign from '@/pages/Campaign'
import { ApiError } from '@/api/client'
import type { CampaignDetail } from '@/types'

const { get, rename, me, toastError, setStatus, removeMember, regen, remove, createSession, share, navigateSpy } = vi.hoisted(() => ({
  get: vi.fn(), rename: vi.fn(), me: vi.fn(), toastError: vi.fn(), setStatus: vi.fn(), removeMember: vi.fn(), regen: vi.fn(), remove: vi.fn(),
  createSession: vi.fn(), share: vi.fn(), navigateSpy: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: {
    campaigns: { get, rename, setMemberStatus: setStatus, removeMember, regenerateCode: regen, remove },
    sessions: { create: createSession, me },
    share: { campaignInvite: share },
  },
  ApiError: class ApiError extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))
vi.mock('@/pages/campaign/LoreSection', () => ({ default: () => null }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ info: vi.fn(), error: toastError, success: vi.fn() }) }))
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
  sessions: [{ id: 8, created_at: '2026-10-28T20:00:00+00:00', duration_seconds: 13200, number: 3, has_recap: true }, { id: 9, created_at: '2026-10-21T20:00:00+00:00', duration_seconds: 14700, number: 2, has_recap: false }, { id: 10, created_at: '2026-10-14T20:00:00+00:00', duration_seconds: 18000, number: 1, has_recap: false }],
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
  it('opens the recap of a night that has one, not of one without', async () => {
    get.mockResolvedValue(detail())
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: /campaign\.night_n/ }))
    expect(navigateSpy).toHaveBeenCalledWith('/campaign/5/recap/8')
    expect(screen.getAllByRole('button', { name: /campaign\.night_n/ })).toHaveLength(1)
  })

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
    // controlli chiusi finché non si tocca «Gestisci»
    expect(screen.queryByRole('button', { name: 'campaign.status_reserve' })).not.toBeInTheDocument()
    await userEvent.click(screen.getAllByRole('button', { name: 'campaign.manage' })[0])
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
    // solo il proprio PG è gestibile ed è etichettato «Tuo»
    expect(screen.getAllByText('campaign.yours')).toHaveLength(1)
    expect(screen.getAllByRole('button', { name: 'campaign.manage' })).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: 'campaign.manage' }))
    expect(screen.getAllByRole('button', { name: 'campaign.status_reserve' })).toHaveLength(1)
    expect(screen.getAllByRole('button', { name: 'campaign.remove_member' })).toHaveLength(1)
    expect(within(screen.getByTestId('members')).getByText('Lyra')).toBeInTheDocument()
  })

  const playerView = (over: Partial<CampaignDetail> = {}) => detail({
    is_gm: false, invite_code: null, active_session_id: 31, my_last_character_id: 10,
    members: [{ character_id: 10, character_name: 'Thorin', class_summary: 'Guerriero 5', total_level: 5, user_id: 2, player_name: 'Aldo', status: 'active', is_mine: true }],
    ...over,
  })

  it('player not yet in the live session gets Entra, which opens the join sheet', async () => {
    get.mockResolvedValue(playerView())
    me.mockResolvedValue(null)
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'campaign.enter' }))
    // seconda «Entra»: quella di conferma dentro lo sheet di scelta del PG
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'campaign.enter' })).toHaveLength(2))
    expect(screen.queryByRole('button', { name: 'campaign.go_to_session' })).not.toBeInTheDocument()
  })

  it('player already in the live session gets Vai alla sessione', async () => {
    get.mockResolvedValue(playerView())
    me.mockResolvedValue({ id: 31, status: 'active' })
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'campaign.go_to_session' }))
    expect(navigateSpy).toHaveBeenCalledWith('/session/31')
    expect(screen.queryByRole('button', { name: 'campaign.enter' })).not.toBeInTheDocument()
  })

  it('player sees no session button when no session is live', async () => {
    get.mockResolvedValue(playerView({ active_session_id: null }))
    renderPage()
    await screen.findByText('Thorin')
    expect(screen.queryByRole('button', { name: 'campaign.enter' })).not.toBeInTheDocument()
  })

  it('GM renames the campaign from the labelled action', async () => {
    get.mockResolvedValue(detail())
    rename.mockResolvedValue({ id: 5, name: 'Nuovo nome', invite_code: 'WIND4242', is_gm: true })
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'campaign.rename' }))
    const input = screen.getByRole('textbox')
    await userEvent.clear(input)
    await userEvent.type(input, '  Nuovo nome ')
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    await waitFor(() => expect(rename).toHaveBeenCalledWith(5, 'Nuovo nome'))
  })

  it('a 409 on start-session toasts that you are in another session', async () => {
    get.mockResolvedValue(detail())
    createSession.mockRejectedValue(new ApiError(409, 'You already have an active session'))
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'campaign.start_session' }))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('session.already_in_other'))
  })

  it('a generic load error offers a retry', async () => {
    get.mockRejectedValueOnce(new Error('offline')).mockResolvedValue(detail())
    renderPage()
    expect(await screen.findByText('campaign.load_error')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'common.retry' }))
    expect(await screen.findByText('Thorin')).toBeInTheDocument()
  })

  it('"my journal" on my character opens the notes filtered by this campaign', async () => {
    get.mockResolvedValue(playerView())
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'campaign.my_journal' }))
    expect(navigateSpy).toHaveBeenCalledWith('/char/10/notes?campaign=5')
  })

  it('no journal link on other players characters', async () => {
    get.mockResolvedValue(detail())
    renderPage()
    await screen.findByText('Thorin')
    expect(screen.queryByRole('button', { name: 'campaign.my_journal' })).not.toBeInTheDocument()
  })
})

import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient } from '@tanstack/react-query'
import { renderWithProviders } from '../../utils/renderWithProviders'
import JoinCampaignSessionSheet from '@/pages/campaign/JoinCampaignSessionSheet'
import CampaignSessionBanner from '@/components/ui/CampaignSessionBanner'

const { get, joinSession, activeForMe, navigateSpy, toastError } = vi.hoisted(() => ({
  get: vi.fn(), joinSession: vi.fn(), activeForMe: vi.fn(), navigateSpy: vi.fn(), toastError: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: { campaigns: { get, joinSession, activeForMe } },
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: unknown) { super('e') }
  },
}))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useNavigate: () => navigateSpy }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string, o?: { name?: string }) => (o?.name ? `${k}:${o.name}` : k), i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: toastError }) }))
vi.mock('@/components/ui/Sheet', () => ({
  default: ({ open, children }: { open: boolean; children: React.ReactNode }) => (open ? <div>{children}</div> : null),
}))

afterEach(() => { get.mockReset(); joinSession.mockReset(); activeForMe.mockReset(); navigateSpy.mockReset(); toastError.mockReset() })

const member = (id: number, name: string, status: string, is_mine = true) => ({
  character_id: id, character_name: name, class_summary: 'X', total_level: 3, user_id: 1, status, is_mine,
})
const item = { campaign_id: 5, campaign_name: 'Coda', session_id: 9, my_last_character_id: 8 }

describe('JoinCampaignSessionSheet', () => {
  it('invalidates the banner query after joining and shows the campaign name', async () => {
    get.mockResolvedValue({ id: 5, members: [member(7, 'Lyra', 'active')] })
    joinSession.mockResolvedValue({ id: 9 })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const spy = vi.spyOn(client, 'invalidateQueries')
    renderWithProviders(<JoinCampaignSessionSheet open onClose={() => {}} item={item} />, { client })
    expect(screen.getByText('Coda')).toBeInTheDocument()
    await screen.findByText('Lyra')
    await userEvent.click(screen.getByRole('button', { name: 'campaign.enter' }))
    await waitFor(() => expect(spy).toHaveBeenCalledWith({ queryKey: ['campaign-active-for-me'] }))
  })

  it.each([
    [409, 'already_active', 'session.already_in_other'],
    [422, 'character_dead', 'campaign.join_err_dead'],
    [404, 'no_active_session', 'campaign.join_err_no_session'],
  ])('maps %i %s to its toast', async (status, detail, key) => {
    const { ApiError } = await import('@/api/client')
    get.mockResolvedValue({ id: 5, members: [member(7, 'Lyra', 'active')] })
    joinSession.mockRejectedValue(new (ApiError as unknown as new (s: number, d: unknown) => Error)(status, detail))
    renderWithProviders(<JoinCampaignSessionSheet open onClose={() => {}} item={item} />)
    await screen.findByText('Lyra')
    await userEvent.click(screen.getByRole('button', { name: 'campaign.enter' }))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith(key))
  })

  it('lists only my non-dead PGs, preselects the last one and joins', async () => {
    get.mockResolvedValue({ id: 5, members: [member(7, 'Lyra', 'active'), member(8, 'Fenn', 'reserve'), member(9, 'Morto', 'dead'), member(10, 'Altrui', 'active', false)] })
    joinSession.mockResolvedValue({ id: 9 })
    renderWithProviders(<JoinCampaignSessionSheet open onClose={() => {}} item={item} />)
    expect(await screen.findByText('Fenn')).toBeInTheDocument()
    expect(screen.queryByText('Morto')).not.toBeInTheDocument()
    expect(screen.queryByText('Altrui')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'campaign.enter' }))
    await waitFor(() => expect(joinSession).toHaveBeenCalledWith(5, 8))
    await waitFor(() => expect(navigateSpy).toHaveBeenCalledWith('/session/9', { replace: true }))
  })

  it('falls back to the first PG when the last one is not available', async () => {
    get.mockResolvedValue({ id: 5, members: [member(7, 'Lyra', 'active'), member(9, 'Morto', 'dead')] })
    joinSession.mockResolvedValue({ id: 9 })
    renderWithProviders(<JoinCampaignSessionSheet open onClose={() => {}} item={item} />)
    await screen.findByText('Lyra')
    await userEvent.click(screen.getByRole('button', { name: 'campaign.enter' }))
    await waitFor(() => expect(joinSession).toHaveBeenCalledWith(5, 7))
  })
})

describe('CampaignSessionBanner', () => {
  it('renders nothing when there is no open campaign session', async () => {
    activeForMe.mockResolvedValue([])
    const { container } = renderWithProviders(<CampaignSessionBanner />)
    await waitFor(() => expect(activeForMe).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('shows a row per open session and opens the join sheet on Entra', async () => {
    activeForMe.mockResolvedValue([item])
    get.mockResolvedValue({ id: 5, members: [member(7, 'Lyra', 'active')] })
    renderWithProviders(<CampaignSessionBanner />)
    expect(await screen.findByText('Coda')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'campaign.enter' }))
    expect(await screen.findByText('Lyra')).toBeInTheDocument()
  })
})

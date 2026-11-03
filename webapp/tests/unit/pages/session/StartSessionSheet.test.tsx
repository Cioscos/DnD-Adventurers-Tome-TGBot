import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import StartSessionSheet from '@/pages/session/StartSessionSheet'

const { list, createCampaign, createSession, navigateSpy } = vi.hoisted(() => ({
  list: vi.fn(), createCampaign: vi.fn(), createSession: vi.fn(), navigateSpy: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: { campaigns: { list, create: createCampaign }, sessions: { create: createSession } },
}))
vi.mock('@/components/ui/Sheet', () => ({
  default: ({ open, title, children }: { open: boolean; title?: string; children: React.ReactNode }) => (open ? <div><h2>{title}</h2>{children}</div> : null),
}))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useNavigate: () => navigateSpy }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))

const camp = (id: number, name: string, is_gm: boolean) => ({
  id, name, is_gm, member_count: 4, last_session_at: '2026-10-28T20:00:00+00:00', active_session_id: null,
})

afterEach(() => { vi.clearAllMocks() })

describe('StartSessionSheet', () => {
  it('lists only GM campaigns, preselects the first and starts the session in it', async () => {
    list.mockResolvedValue([camp(1, 'Coda del Vento', true), camp(2, 'Da giocatore', false), camp(3, 'Phandalin', true)])
    createSession.mockResolvedValue({ id: 9 })
    renderWithProviders(<StartSessionSheet open onClose={() => {}} />)
    const first = await screen.findByRole('button', { name: /Coda del Vento/ })
    await waitFor(() => expect(first).toHaveAttribute('aria-pressed', 'true'))
    expect(screen.getByText('campaign.start_title')).toBeInTheDocument()
    expect(screen.queryByText(/Da giocatore/)).not.toBeInTheDocument()
    expect(first).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'campaign.start_go' }))
    await waitFor(() => expect(createSession).toHaveBeenCalledWith(undefined, 1))
    await waitFor(() => expect(navigateSpy).toHaveBeenCalledWith('/session/9'))
  })

  it('"Nessuna" starts a one-off session without campaign', async () => {
    list.mockResolvedValue([camp(1, 'Coda del Vento', true)])
    createSession.mockResolvedValue({ id: 4 })
    renderWithProviders(<StartSessionSheet open onClose={() => {}} />)
    await userEvent.click(await screen.findByRole('button', { name: /campaign\.none/ }))
    await userEvent.click(screen.getByRole('button', { name: 'campaign.start_go' }))
    await waitFor(() => expect(createSession).toHaveBeenCalledWith())
    await waitFor(() => expect(navigateSpy).toHaveBeenCalledWith('/session/4'))
  })

  it('with no campaigns preselects "Nessuna" and offers a new campaign', async () => {
    list.mockResolvedValue([])
    renderWithProviders(<StartSessionSheet open onClose={() => {}} />)
    const none = await screen.findByRole('button', { name: /campaign\.none/ })
    await waitFor(() => expect(none).toHaveAttribute('aria-pressed', 'true'))
    expect(screen.getByRole('button', { name: /campaign\.new/ })).toBeInTheDocument()
  })

  it('"+ Nuova campagna" creates the campaign and starts the session in it', async () => {
    list.mockResolvedValue([])
    createCampaign.mockResolvedValue({ id: 12, name: 'Nuova', is_gm: true })
    createSession.mockResolvedValue({ id: 30 })
    renderWithProviders(<StartSessionSheet open onClose={() => {}} />)
    await userEvent.click(await screen.findByRole('button', { name: /campaign\.new/ }))
    expect(screen.getByRole('button', { name: 'campaign.start_go' })).toBeDisabled()
    await userEvent.type(screen.getByPlaceholderText('campaign.new_name_placeholder'), 'Nuova')
    await userEvent.click(screen.getByRole('button', { name: 'campaign.start_go' }))
    await waitFor(() => expect(createCampaign).toHaveBeenCalledWith('Nuova'))
    await waitFor(() => expect(createSession).toHaveBeenCalledWith(undefined, 12))
    await waitFor(() => expect(navigateSpy).toHaveBeenCalledWith('/session/30'))
  })

  it('retrying after a failed session start does not create a second campaign', async () => {
    list.mockResolvedValue([])
    createCampaign.mockResolvedValue({ id: 12, name: 'Nuova', is_gm: true })
    createSession.mockRejectedValueOnce(new Error('boom')).mockResolvedValue({ id: 30 })
    renderWithProviders(<StartSessionSheet open onClose={() => {}} />)
    await userEvent.click(await screen.findByRole('button', { name: /campaign\.new/ }))
    await userEvent.type(screen.getByPlaceholderText('campaign.new_name_placeholder'), 'Nuova')
    await userEvent.click(screen.getByRole('button', { name: 'campaign.start_go' }))
    await waitFor(() => expect(createSession).toHaveBeenCalledTimes(1))
    await userEvent.click(await screen.findByRole('button', { name: 'campaign.start_go' }))
    await waitFor(() => expect(createSession).toHaveBeenCalledTimes(2))
    expect(createCampaign).toHaveBeenCalledTimes(1)
    expect(createSession).toHaveBeenLastCalledWith(undefined, 12)
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AllyReactionPrompt from '@/components/session/AllyReactionPrompt'

const { api, toastMock, ApiErrorMock } = vi.hoisted(() => {
  class ApiErrorMock extends Error { constructor(public status: number, public detail: unknown) { super('x') } }
  return {
    ApiErrorMock,
    toastMock: Object.assign(vi.fn(), { error: vi.fn(), success: vi.fn(), info: vi.fn() }),
    api: {
      sessions: { me: vi.fn() },
      allyReactions: { prompts: vi.fn(), answer: vi.fn() },
    },
  }
})
vi.mock('@/api/client', () => ({ api, ApiError: ApiErrorMock }))
vi.mock('sonner', () => ({ toast: toastMock }))
vi.mock('@/lib/mutationError', () => ({ notifyMutationError: vi.fn() }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/components/ui/Sheet', () => ({
  default: ({ open, children }: { open: boolean; children: React.ReactNode }) => (open ? <div>{children}</div> : null),
}))

const prompt = (over = {}) => ({
  request_id: 5, receiver_name: 'Bruno', damage: 12, damage_type: 'slashing',
  feature_key: 'fighter.style_interception', dice: '1d10+2', ...over,
})

function setup(prompts: unknown[]) {
  api.sessions.me.mockResolvedValue({ id: 1, status: 'active', participants: [{ character_id: 7 }] })
  api.allyReactions.prompts.mockResolvedValue(prompts)
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={qc}><AllyReactionPrompt charId={7} /></QueryClientProvider>)
}

describe('AllyReactionPrompt', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('shows receiver, damage and the Interception question', async () => {
    setup([prompt()])
    expect(await screen.findByText('È il colpo di un attacco e sei entro 1,5 m da Bruno?')).toBeInTheDocument()
    expect(screen.getAllByText(/Bruno/).length).toBeGreaterThan(0)
    expect(screen.getByText(/12/)).toBeInTheDocument()
  })

  it('asks the Cutting Words question', async () => {
    setup([prompt({ feature_key: 'bard.cutting_words', dice: '1d6' })])
    expect(await screen.findByText('Vedi la creatura entro 18 m?')).toBeInTheDocument()
  })

  it('shows nothing without prompts', async () => {
    setup([])
    await waitFor(() => expect(api.allyReactions.prompts).toHaveBeenCalled())
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('Usa answers use:true', async () => {
    api.allyReactions.answer.mockResolvedValue({ reduction: 7, rolls: [5] })
    setup([prompt()])
    await userEvent.click(await screen.findByRole('button', { name: 'Usa' }))
    expect(api.allyReactions.answer).toHaveBeenCalledWith(7, 5, true)
  })

  it('Lascia answers use:false', async () => {
    api.allyReactions.answer.mockResolvedValue({ reduction: 0, rolls: [] })
    setup([prompt()])
    await userEvent.click(await screen.findByRole('button', { name: 'Lascia' }))
    expect(api.allyReactions.answer).toHaveBeenCalledWith(7, 5, false)
  })

  it('a 409 closes the popup with a toast', async () => {
    api.allyReactions.answer.mockRejectedValue(new ApiErrorMock(409, { code: 'request_closed' }))
    setup([prompt()])
    await userEvent.click(await screen.findByRole('button', { name: 'Usa' }))
    await waitFor(() => expect(toastMock.error).toHaveBeenCalled())
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Usa' })).not.toBeInTheDocument())
  })
})

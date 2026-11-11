import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useAllyReactionWait } from '@/hooks/useAllyReactionWait'

const { api } = vi.hoisted(() => ({
  api: { allyReactions: { open: vi.fn(), read: vi.fn(), close: vi.fn() } },
}))
vi.mock('@/api/client', () => ({ api }))
vi.mock('@/components/ui/Sheet', () => ({
  default: ({ open, children }: { open: boolean; children: React.ReactNode }) => (open ? <div>{children}</div> : null),
}))

function Harness({ onDone }: { onDone: (id: number | null) => void }) {
  const { wait, elements } = useAllyReactionWait(7)
  return (
    <>
      <button onClick={() => wait(10, 'slashing').then(onDone)}>go</button>
      {elements}
    </>
  )
}

const empty = { waiting: [], answers: [], total_reduction: 0 }

describe('useAllyReactionWait', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('does not wait when no request is opened', async () => {
    api.allyReactions.open.mockResolvedValue({ request_id: null, waiting: [], expires_in: 0 })
    const done = vi.fn()
    render(<Harness onDone={done} />)
    await userEvent.click(screen.getByText('go'))
    await waitFor(() => expect(done).toHaveBeenCalledWith(null))
    expect(screen.queryByText(/In attesa di/)).not.toBeInTheDocument()
  })

  it('lists who is awaited and closes on the skip button', async () => {
    api.allyReactions.open.mockResolvedValue({
      request_id: 3, expires_in: 30,
      waiting: [{ character_id: 1, name: 'Aldo', feature_key: 'x' }, { character_id: 2, name: 'Cora', feature_key: 'y' }],
    })
    api.allyReactions.read.mockResolvedValue({ status: 'open', ...empty })
    api.allyReactions.close.mockResolvedValue({ status: 'closed', ...empty })
    const done = vi.fn()
    render(<Harness onDone={done} />)
    await userEvent.click(screen.getByText('go'))
    expect(await screen.findByText('In attesa di: Aldo, Cora')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Applica senza aspettare' }))
    expect(api.allyReactions.close).toHaveBeenCalledWith(7, 3)
    await waitFor(() => expect(done).toHaveBeenCalledWith(3))
    expect(screen.queryByText(/In attesa di/)).not.toBeInTheDocument()
  })

  it('leaving the page during the wait closes the request and lets the damage go on', async () => {
    api.allyReactions.open.mockResolvedValue({ request_id: 3, expires_in: 30, waiting: [{ character_id: 1, name: 'Aldo', feature_key: 'x' }] })
    api.allyReactions.read.mockResolvedValue({ status: 'open', ...empty })
    api.allyReactions.close.mockResolvedValue({ status: 'closed', ...empty })
    const done = vi.fn()
    const { unmount } = render(<Harness onDone={done} />)
    await userEvent.click(screen.getByText('go'))
    await screen.findByText('In attesa di: Aldo')
    unmount()
    expect(api.allyReactions.close).toHaveBeenCalledWith(7, 3)
    await waitFor(() => expect(done).toHaveBeenCalledWith(3))
  })

  it('continues by itself when the poll says closed', async () => {
    api.allyReactions.open.mockResolvedValue({ request_id: 4, expires_in: 30, waiting: [{ character_id: 1, name: 'Aldo', feature_key: 'x' }] })
    api.allyReactions.read.mockResolvedValue({ status: 'closed', ...empty, total_reduction: 5 })
    const done = vi.fn()
    render(<Harness onDone={done} />)
    await userEvent.click(screen.getByText('go'))
    await waitFor(() => expect(done).toHaveBeenCalledWith(4), { timeout: 4000 })
  })
})

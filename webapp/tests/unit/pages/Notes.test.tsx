import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient } from '@tanstack/react-query'
import { renderWithProviders } from '../utils/renderWithProviders'
import Notes from '@/pages/Notes'

const { list, campaigns } = vi.hoisted(() => ({ list: vi.fn(), campaigns: vi.fn() }))

vi.mock('@/api/client', () => {
  class ApiError extends Error {
    constructor(public status: number, public detail: unknown) { super(`API ${status}`) }
  }
  return { api: { notes: { list, campaigns, voiceUrl: () => '' }, share: { note: vi.fn() } }, ApiError }
})
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '7' }) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }), canShareMessage: () => false }))
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'drag', 'layout'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return {
    m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }),
    AnimatePresence: (p: { children?: unknown }) => p.children,
    useReducedMotion: () => false,
  }
})
// Il Layout vero è coperto a parte: qui serve vedere quale query gli passa la pagina.
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  const { default: OfflineNotice } = await import('@/components/ui/OfflineNotice')
  return {
    default: (p: { children?: unknown; offlineQuery?: never; backTo?: string }) =>
      React.createElement('div', { 'data-testid': 'layout', 'data-back': p.backTo }, p.offlineQuery ? React.createElement(OfflineNotice, { query: p.offlineQuery }) : null, p.children),
  }
})
vi.mock('@/components/ScrollArea', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/Sheet', () => ({ default: () => null }))
vi.mock('@/components/ui/ConfirmSheet', () => ({ default: () => null }))
vi.mock('@/pages/notes/NoteViewModal', () => ({ default: () => null }))
vi.mock('@/pages/notes/NoteItem', async () => {
  const React = await import('react')
  return { default: (p: { note: { title: string } }) => React.createElement('div', null, p.note.title) }
})
vi.mock('@/components/skeletons/NotesSkeleton', () => ({ default: () => null }))

afterEach(() => { list.mockReset(); campaigns.mockReset() })
beforeEach(() => { campaigns.mockResolvedValue([]) })

describe('Notes', () => {
  it('shows the empty state when there really are no notes', async () => {
    list.mockResolvedValue([])
    renderWithProviders(<Notes />)
    expect(await screen.findByText('character.notes.empty_title')).toBeInTheDocument()
  })

  it('failed fetch without cache shows offline unavailable, not empty', async () => {
    list.mockRejectedValue(new TypeError('Failed to fetch'))
    renderWithProviders(<Notes />)
    expect(await screen.findByText('common.offline_unavailable')).toBeInTheDocument()
    expect(screen.queryByText('character.notes.empty_title')).not.toBeInTheDocument()
  })

  it('retries from the offline state', async () => {
    list.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    renderWithProviders(<Notes />)
    await screen.findByText('common.offline_unavailable')
    list.mockResolvedValue([{ title: 'Taverna', body: 'x', is_voice: false, tags: [] }])
    await userEvent.click(screen.getByRole('button', { name: 'common.retry' }))
    expect(await screen.findByText('Taverna')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByText('common.offline_unavailable')).not.toBeInTheDocument())
  })

  it('keeps cached notes and flags them when the refetch fails for network', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    client.setQueryData(['notes', 7], [{ title: 'Taverna', body: 'x', is_voice: false, tags: [] }])
    list.mockRejectedValue(new TypeError('Failed to fetch'))
    renderWithProviders(<Notes />, { client })
    expect(screen.getByText('Taverna')).toBeInTheDocument()
    expect(await screen.findByText('common.offline_data_from')).toBeInTheDocument()
  })
})

const n = (title: string, campaign_id: number | null, campaign_name: string | null) =>
  ({ title, body: 'x', is_voice: false, tags: [], campaign_id, campaign_name })

describe('Notes campaign filter', () => {
  beforeEach(() => {
    campaigns.mockResolvedValue([{ id: 7, name: 'Coda', current: true }, { id: 8, name: 'Altra', current: false }])
    list.mockResolvedValue([n('Taverna', 7, 'Coda'), n('Faro', 8, 'Altra'), n('Libera', null, null)])
  })

  it('uses the Diario title and shows all entries by default', async () => {
    renderWithProviders(<Notes />)
    expect(await screen.findByText('Taverna')).toBeInTheDocument()
    expect(screen.getByText('Faro')).toBeInTheDocument()
    expect(screen.getByText('Libera')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'character.notes.filter_all' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'character.notes.filter_none' })).toBeInTheDocument()
  })

  it('choosing a campaign shows only its entries', async () => {
    renderWithProviders(<Notes />)
    await userEvent.click(await screen.findByRole('button', { name: 'Altra' }))
    expect(screen.getByText('Faro')).toBeInTheDocument()
    expect(screen.queryByText('Taverna')).not.toBeInTheDocument()
    expect(screen.queryByText('Libera')).not.toBeInTheDocument()
  })

  it('entries without campaign appear under "no campaign"', async () => {
    renderWithProviders(<Notes />)
    await userEvent.click(await screen.findByRole('button', { name: 'character.notes.filter_none' }))
    expect(screen.getByText('Libera')).toBeInTheDocument()
    expect(screen.queryByText('Taverna')).not.toBeInTheDocument()
  })

  it('back arrow returns to the campaign when opened from it', () => {
    renderWithProviders(<Notes />, { route: { pathname: '/', search: '?campaign=7', state: { from: '/campaign/7' } } })
    expect(screen.getAllByTestId('layout').at(-1)).toHaveAttribute('data-back', '/campaign/7')
  })

  it('back arrow returns to the sheet by default', () => {
    renderWithProviders(<Notes />)
    expect(screen.getAllByTestId('layout').at(-1)).toHaveAttribute('data-back', '/char/7')
  })

  it('?campaign=7 preselects that campaign', async () => {
    renderWithProviders(<Notes />, { route: '/?campaign=7' })
    expect(await screen.findByText('Taverna')).toBeInTheDocument()
    expect(screen.queryByText('Faro')).not.toBeInTheDocument()
  })

  it('?campaign=none preselects "no campaign"', async () => {
    renderWithProviders(<Notes />, { route: '/?campaign=none' })
    expect(await screen.findByText('Libera')).toBeInTheDocument()
    expect(screen.queryByText('Taverna')).not.toBeInTheDocument()
  })

  it('an entry of a deleted campaign (id kept, name null) is under "no campaign" only', async () => {
    list.mockResolvedValue([n('Orfana', 99, null), n('Taverna', 7, 'Coda')])
    renderWithProviders(<Notes />)
    await userEvent.click(await screen.findByRole('button', { name: 'character.notes.filter_none' }))
    expect(screen.getByText('Orfana')).toBeInTheDocument()
    expect(screen.queryByText('Taverna')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Coda' }))
    expect(screen.queryByText('Orfana')).not.toBeInTheDocument()
  })

  it('?campaign=<unknown id> falls back to all', async () => {
    renderWithProviders(<Notes />, { route: '/?campaign=55' })
    expect(await screen.findByText('Taverna')).toBeInTheDocument()
    expect(screen.getByText('Faro')).toBeInTheDocument()
  })
})

import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient } from '@tanstack/react-query'
import { renderWithProviders } from '../utils/renderWithProviders'
import Notes from '@/pages/Notes'

const { list } = vi.hoisted(() => ({ list: vi.fn() }))

vi.mock('@/api/client', () => {
  class ApiError extends Error {
    constructor(public status: number, public detail: unknown) { super(`API ${status}`) }
  }
  return { api: { notes: { list, voiceUrl: () => '' }, share: { note: vi.fn() } }, ApiError }
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
    default: (p: { children?: unknown; offlineQuery?: never }) =>
      React.createElement('div', null, p.offlineQuery ? React.createElement(OfflineNotice, { query: p.offlineQuery }) : null, p.children),
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

afterEach(() => { list.mockReset() })

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

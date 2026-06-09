import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import History from '@/pages/History'

const { get, clear } = vi.hoisted(() => ({ get: vi.fn(), clear: vi.fn() }))

vi.mock('@/api/client', () => ({ api: { history: { get, clear } } }))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '7' }) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/lib/relativeTime', () => ({ formatRelative: () => '5 min fa', formatAbsolute: () => '1 gennaio' }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'drag', 'layout'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return { m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }) }
})
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ScrollArea', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/Skeleton', async () => {
  const React = await import('react')
  const S = () => React.createElement('div', { 'data-testid': 'skeleton' })
  return { default: { Line: S, Rect: S, Circle: S } }
})
vi.mock('@/components/ui/EmptyState', async () => {
  const React = await import('react')
  return { default: (p: { title?: unknown }) => React.createElement('div', null, p.title) }
})
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void; loading?: boolean; children?: unknown }) => React.createElement('button', { onClick: p.onClick, disabled: p.loading }, p.children) }
})

afterEach(() => { get.mockReset(); clear.mockReset() })

describe('History', () => {
  it('shows the empty state when there is no history', async () => {
    get.mockResolvedValue([])
    renderWithProviders(<History />)
    expect(await screen.findByText('character.history.empty')).toBeInTheDocument()
  })

  it('renders history entries on the timeline', async () => {
    get.mockResolvedValue([{ id: 1, timestamp: '2026-06-01T10:00:00Z', event_type: 'hp_change', description: 'Curato di 5 PF' }])
    renderWithProviders(<History />)
    expect(await screen.findByText('Curato di 5 PF')).toBeInTheDocument()
  })

  it('clears the history through the confirm sheet', async () => {
    get.mockResolvedValue([{ id: 1, timestamp: '2026-06-01T10:00:00Z', event_type: 'hp_change', description: 'Evento' }])
    clear.mockResolvedValue(undefined)
    renderWithProviders(<History />)
    await screen.findByText('Evento')
    await userEvent.click(screen.getByRole('button', { name: 'character.history.clear' }))
    await userEvent.click(screen.getByRole('button', { name: 'common.confirm' }))
    await waitFor(() => expect(clear).toHaveBeenCalledWith(7))
  })
})

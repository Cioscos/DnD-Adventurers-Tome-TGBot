import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient } from '@tanstack/react-query'
import { renderWithProviders } from '../utils/renderWithProviders'
import CharacterMain from '@/pages/CharacterMain'
import { ApiError } from '@/api/client'

const { getChar, updateInspiration, navigateSpy } = vi.hoisted(() => ({ getChar: vi.fn(), updateInspiration: vi.fn(), navigateSpy: vi.fn() }))

vi.mock('@/api/client', () => {
  // Speculare alla classe reale: CharacterMain fa `instanceof ApiError` e
  // legge `.status` per distinguere 404/403 dagli errori generici.
  class ApiError extends Error {
    constructor(
      public status: number,
      public detail: unknown,
    ) {
      super(`API ${status}`)
      this.name = 'ApiError'
    }
  }
  return { api: { characters: { get: getChar, updateInspiration } }, ApiError }
})
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '7' }), useNavigate: () => navigateSpy }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/store/characterStore', () => ({ useCharacterStore: (sel: (s: { setActiveCharId: (n: number) => void }) => unknown) => sel({ setActiveCharId: () => {} }) }))
vi.mock('@/styles/motion', () => ({ spring: new Proxy({}, { get: () => ({}) }) }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
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
    AnimatePresence: (p: { children?: unknown }) => React.createElement(React.Fragment, null, p.children),
    // SearchOverlay monta Sheet, che usa il drag-to-dismiss dal giro r2.
    useDragControls: () => ({ start: () => {} }),
  }
})
vi.mock('@/components/ui/Skeleton', async () => {
  const React = await import('react')
  const S = () => React.createElement('div', { 'data-testid': 'skeleton' })
  return { default: { Line: S, Rect: S, Circle: S } }
})
vi.mock('@/components/ui/InSessionBanner', () => ({ default: () => null }))
vi.mock('@/components/PendingSavesBanner', () => ({ default: () => null }))
vi.mock('@/components/character/CharacterSwiper', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'swiper' }) }
})

afterEach(() => { getChar.mockReset(); updateInspiration.mockReset(); navigateSpy.mockReset() })

describe('CharacterMain', () => {
  it('shows skeletons while the character query is pending', () => {
    getChar.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<CharacterMain />)
    expect(screen.getAllByTestId('skeleton').length).toBeGreaterThan(0)
  })

  it('renders the character name and the swiper once loaded', async () => {
    getChar.mockResolvedValue({ id: 7, name: 'Aragorn', heroic_inspiration: false })
    renderWithProviders(<CharacterMain />)
    expect(await screen.findByText('Aragorn')).toBeInTheDocument()
    expect(screen.getByTestId('swiper')).toBeInTheDocument()
  })

  it('toggles heroic inspiration through the API', async () => {
    getChar.mockResolvedValue({ id: 7, name: 'Aragorn', heroic_inspiration: false })
    updateInspiration.mockResolvedValue({ id: 7, name: 'Aragorn', heroic_inspiration: true })
    renderWithProviders(<CharacterMain />)
    await screen.findByText('Aragorn')
    await userEvent.click(screen.getByRole('button', { name: 'character.inspiration.aria' }))
    await waitFor(() => expect(updateInspiration).toHaveBeenCalledWith(7, true))
  })

  it('shows a retryable error state when the character fails to load', async () => {
    getChar.mockRejectedValue(new Error('boom'))
    renderWithProviders(<CharacterMain />)
    expect(await screen.findByText('layout.char_error.generic')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'layout.char_error.retry' })).toBeInTheDocument()
  })

  it('shows the not-found state with a back-to-list CTA on 404', async () => {
    getChar.mockRejectedValue(new ApiError(404, 'not found'))
    renderWithProviders(<CharacterMain />)
    expect(await screen.findByText('layout.char_error.not_found')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'layout.char_error.back_to_list' }))
    expect(navigateSpy).toHaveBeenCalledWith('/')
  })

  const cachedClient = () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, retryDelay: 0 } } })
    // Niente staleTime in questo client: al montaggio parte subito il refetch.
    client.setQueryData(['character', 7], { id: 7, name: 'Aragorn', heroic_inspiration: false })
    return client
  }

  it('keeps cached sheet when refetch fails for network', async () => {
    getChar.mockRejectedValue(new TypeError('Failed to fetch'))
    renderWithProviders(<CharacterMain />, { client: cachedClient() })
    expect(await screen.findByText('common.offline_data_from')).toBeInTheDocument()
    expect(screen.getByText('Aragorn')).toBeInTheDocument()
    expect(screen.getByTestId('swiper')).toBeInTheDocument()
    expect(screen.queryByText('layout.char_error.generic')).not.toBeInTheDocument()
  })

  it('shows not found when refetch returns 404 despite cache', async () => {
    getChar.mockRejectedValue(new ApiError(404, 'not found'))
    renderWithProviders(<CharacterMain />, { client: cachedClient() })
    expect(await screen.findByText('layout.char_error.not_found')).toBeInTheDocument()
    expect(screen.queryByTestId('swiper')).not.toBeInTheDocument()
  })

  it.each([500, 401])('keeps the sheet and says it is not updated on a %i', async (status) => {
    getChar.mockRejectedValue(new ApiError(status, 'boom'))
    renderWithProviders(<CharacterMain />, { client: cachedClient() })
    await waitFor(() => expect(getChar).toHaveBeenCalledTimes(4))
    expect(await screen.findByText('common.stale_data_from')).toBeInTheDocument()
    expect(screen.getByText('Aragorn')).toBeInTheDocument()
    expect(screen.queryByText('common.offline_data_from')).not.toBeInTheDocument()
    expect(screen.queryByText('layout.char_error.not_found')).not.toBeInTheDocument()
  })

  it('shows not found when refetch returns 403 despite cache', async () => {
    getChar.mockRejectedValue(new ApiError(403, 'forbidden'))
    renderWithProviders(<CharacterMain />, { client: cachedClient() })
    expect(await screen.findByText('layout.char_error.not_found')).toBeInTheDocument()
    expect(screen.queryByText('common.stale_data_from')).not.toBeInTheDocument()
  })
})

import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render as rtlRender, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import userEvent from '@testing-library/user-event'
import Layout from '@/components/Layout'
import { api, ApiError } from '@/api/client'

// Il guard condiviso del Layout (batch B3) usa useQuery + ApiError: serve un
// QueryClient nel tree e un client API mockato (qui: query sempre pending,
// così i children renderizzano come nel caso felice).
const render = (ui: React.ReactElement) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return rtlRender(ui, {
    wrapper: ({ children }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>,
  })
}

beforeAll(() => {
  // jsdom lacks Element.scrollBy — the breadcrumb auto-scroll effect calls it.
  Element.prototype.scrollBy = vi.fn()
})

type Info = { pages: string[]; index: number; total: number } | null
const { navigateSpy, goToPageSpy, groupInfo } = vi.hoisted(() => ({ navigateSpy: vi.fn(), goToPageSpy: vi.fn(), groupInfo: { value: null as Info } }))

vi.mock('react-router-dom', () => ({ useNavigate: () => navigateSpy, useParams: () => ({ id: '7' }), useLocation: () => ({ pathname: '/char/7' }) }))
vi.mock('@/api/client', () => ({
  api: { characters: { get: vi.fn(() => new Promise(() => {})) } },
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: unknown) { super('api error') }
  },
}))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/hooks/useSwipeNavigation', () => ({
  useSwipeNavigation: () => ({ contentRef: { current: null }, ghostRef: { current: null }, ghostDir: 0, onTouchStart() {}, onTouchMove() {}, onTouchEnd() {}, goToPage: goToPageSpy, currentIndex: 0, total: 1 }),
  getGroupInfo: () => groupInfo.value,
}))
vi.mock('@/components/skeletons/pageSkeletons', () => ({ pageSkeleton: () => () => null }))
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
  }
})

afterEach(() => {
  navigateSpy.mockReset()
  groupInfo.value = null
})

describe('Layout', () => {
  describe('character guard with a cached sheet', () => {
    const cachedRender = (ui: React.ReactElement, { cached = true } = {}) => {
      // retryDelay 0: il guard ha una sua politica di retry, senza backoff nel test.
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false, retryDelay: 0 } } })
      if (cached) qc.setQueryData(['character', 7], { id: 7, name: 'Aragorn' })
      return rtlRender(ui, {
        wrapper: ({ children }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>,
      })
    }

    afterEach(() => {
      vi.mocked(api.characters.get).mockImplementation(() => new Promise(() => {}))
    })

    it('keeps the page and shows the notice when the refetch fails for network', async () => {
      vi.mocked(api.characters.get).mockRejectedValue(new TypeError('Failed to fetch'))
      cachedRender(<Layout title="T"><p>contenuto</p></Layout>)
      expect(await screen.findByText('common.offline_data_from')).toBeInTheDocument()
      expect(screen.getByText('contenuto')).toBeInTheDocument()
      expect(screen.queryByText('layout.char_error.generic')).not.toBeInTheDocument()
    })

    it('keeps the page with the neutral notice on a 500', async () => {
      vi.mocked(api.characters.get).mockRejectedValue(new ApiError(500, 'boom'))
      cachedRender(<Layout title="T"><p>contenuto</p></Layout>)
      expect(await screen.findByText('common.stale_data_from')).toBeInTheDocument()
      expect(screen.getByText('contenuto')).toBeInTheDocument()
    })

    it('shows not found on 404 even with a cached sheet', async () => {
      vi.mocked(api.characters.get).mockRejectedValue(new ApiError(404, 'gone'))
      cachedRender(<Layout title="T"><p>contenuto</p></Layout>)
      expect(await screen.findByText('layout.char_error.not_found')).toBeInTheDocument()
      expect(screen.queryByText('contenuto')).not.toBeInTheDocument()
    })

    it('shows the retry state when there is no cached sheet', async () => {
      vi.mocked(api.characters.get).mockRejectedValue(new TypeError('Failed to fetch'))
      cachedRender(<Layout title="T"><p>contenuto</p></Layout>, { cached: false })
      expect(await screen.findByText('layout.char_error.generic')).toBeInTheDocument()
      expect(screen.queryByText('contenuto')).not.toBeInTheDocument()
    })

    it('reports on the page query when one is given', async () => {
      const failedNotes = { data: [], dataUpdatedAt: Date.now(), error: new TypeError('x'), failureReason: null, isFetching: false, isRefetchError: true }
      cachedRender(<Layout title="T" offlineQuery={failedNotes}><p>contenuto</p></Layout>)
      expect(await screen.findByText('common.offline_data_from')).toBeInTheDocument()
      expect(screen.getByText('contenuto')).toBeInTheDocument()
    })
  })

  it('renders the title, children and a back button', () => {
    render(<Layout title="Punti Ferita">corpo pagina</Layout>)
    expect(screen.getByRole('heading', { name: 'Punti Ferita' })).toBeInTheDocument()
    expect(screen.getByText('corpo pagina')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'common.back' })).toBeInTheDocument()
  })

  it('navigates to backTo when provided, else steps back in history', async () => {
    const { rerender } = render(<Layout title="T" backTo="/char/7">x</Layout>)
    await userEvent.click(screen.getByRole('button', { name: 'common.back' }))
    expect(navigateSpy).toHaveBeenCalledWith('/char/7')
    navigateSpy.mockReset()
    rerender(<Layout title="T">x</Layout>)
    await userEvent.click(screen.getByRole('button', { name: 'common.back' }))
    expect(navigateSpy).toHaveBeenCalledWith(-1)
  })

  it('renders a breadcrumb and navigates to a tapped sibling page', async () => {
    groupInfo.value = { pages: ['hp', 'ac', 'saves', 'actions'], index: 1, total: 4 }
    render(<Layout title="T" group="combat" page="ac">x</Layout>)
    await userEvent.click(screen.getByText('character.menu.hp'))
    expect(goToPageSpy).toHaveBeenCalledWith('hp')
  })

  it('omits the breadcrumb when there is no group info', () => {
    groupInfo.value = null
    render(<Layout title="T">x</Layout>)
    expect(screen.queryByText('character.menu.hp')).not.toBeInTheDocument()
  })
})

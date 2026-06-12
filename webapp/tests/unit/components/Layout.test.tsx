import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render as rtlRender, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import userEvent from '@testing-library/user-event'
import Layout from '@/components/Layout'

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
const { navigateSpy, groupInfo } = vi.hoisted(() => ({ navigateSpy: vi.fn(), groupInfo: { value: null as Info } }))

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
  useSwipeNavigation: () => ({ contentRef: { current: null }, ghostRef: { current: null }, ghostDir: 0, onTouchStart() {}, onTouchMove() {}, onTouchEnd() {}, currentIndex: 0, total: 1 }),
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
  it('renders the title, children and a back button', () => {
    render(<Layout title="Punti Ferita">corpo pagina</Layout>)
    expect(screen.getByRole('heading', { name: 'Punti Ferita' })).toBeInTheDocument()
    expect(screen.getByText('corpo pagina')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Indietro' })).toBeInTheDocument()
  })

  it('navigates to backTo when provided, else steps back in history', async () => {
    const { rerender } = render(<Layout title="T" backTo="/char/7">x</Layout>)
    await userEvent.click(screen.getByRole('button', { name: 'Indietro' }))
    expect(navigateSpy).toHaveBeenCalledWith('/char/7')
    navigateSpy.mockReset()
    rerender(<Layout title="T">x</Layout>)
    await userEvent.click(screen.getByRole('button', { name: 'Indietro' }))
    expect(navigateSpy).toHaveBeenCalledWith(-1)
  })

  it('renders a breadcrumb and navigates to a tapped sibling page', async () => {
    groupInfo.value = { pages: ['hp', 'ac', 'saves', 'actions'], index: 1, total: 4 }
    render(<Layout title="T" group="combat" page="ac">x</Layout>)
    await userEvent.click(screen.getByText('character.menu.hp'))
    expect(navigateSpy).toHaveBeenCalledWith('/char/7/hp', { replace: true })
  })

  it('omits the breadcrumb when there is no group info', () => {
    groupInfo.value = null
    render(<Layout title="T">x</Layout>)
    expect(screen.queryByText('character.menu.hp')).not.toBeInTheDocument()
  })
})

import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../utils/renderWithProviders'
import AtlasMap from '@/pages/AtlasMap'

const { maps, markers, getCampaign, navigateSpy, setTransform, ApiError } = vi.hoisted(() => ({
  maps: vi.fn(), markers: vi.fn(), getCampaign: vi.fn(), navigateSpy: vi.fn(), setTransform: vi.fn(),
  ApiError: class ApiError extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))

vi.mock('@/api/client', () => ({
  api: {
    atlas: { maps, markers, mapImageUrl: () => 'http://x/img' },
    campaigns: { get: getCampaign },
  },
  ApiError,
}))
vi.mock('react-zoom-pan-pinch', async () => {
  const React = await import('react')
  return {
    TransformWrapper: React.forwardRef((p: { children?: React.ReactNode }, ref) => {
      React.useImperativeHandle(ref, () => ({
        setTransform, zoomIn: vi.fn(), zoomOut: vi.fn(),
        instance: { transformState: { positionX: 0, positionY: 0, scale: 1 } },
      }))
      return React.createElement('div', null, p.children)
    }),
    TransformComponent: (p: { children?: React.ReactNode }) => React.createElement('div', null, p.children),
  }
})
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useNavigate: () => navigateSpy }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))

const type = { id: null, key: 'city', name: 'city', icon: 'castle', color: 'gold', builtin: true, can_delete: false }
const mk = (id: number, over = {}) => ({
  id, map_id: 9, name: `M${id}`, description: '', x: 0.5, y: 0.5, visibility: 'public', type,
  author_role: 'gm', author_name: null, mine: false, link_map_id: null, can_edit: false, can_delete: false,
  updated_at: 'x', ...over,
})
const theMap = { id: 9, name: 'Faerûn', revealed: true, revealed_at: null, updated_at: 'u', marker_count: 3 }

function setup({ gm = false, list = [mk(1), mk(2, { author_role: 'player', author_name: 'Ari' }), mk(3, { author_role: 'player', mine: true })], route = '/campaign/3/atlas/9' as string | { pathname: string; search?: string; state?: unknown } } = {}) {
  maps.mockResolvedValue([theMap])
  markers.mockResolvedValue(list)
  getCampaign.mockResolvedValue({ id: 3, name: 'C', is_gm: gm })
  return renderWithProviders(
    <Routes><Route path="/campaign/:id/atlas/:mapId" element={<AtlasMap />} /></Routes>,
    { route },
  )
}
const pins = () => document.querySelectorAll('[data-pin]')

afterEach(() => { [maps, markers, getCampaign, navigateSpy, setTransform].forEach((f) => f.mockReset()) })

describe('AtlasMap', () => {
  it('renders one pin per marker', async () => {
    setup()
    await waitFor(() => expect(pins()).toHaveLength(3))
    expect(await screen.findByText('Faerûn')).toBeTruthy()
  })

  it('filter Miei shows only mine and is hidden for GM', async () => {
    const { unmount } = setup()
    await waitFor(() => expect(pins()).toHaveLength(3))
    await userEvent.click(screen.getByRole('button', { name: 'atlas.filter_mine' }))
    expect(pins()).toHaveLength(1)
    expect(pins()[0].getAttribute('data-pin')).toBe('3')
    await userEvent.click(screen.getByRole('button', { name: 'atlas.filter_group' }))
    expect([...pins()].map((p) => p.getAttribute('data-pin'))).toEqual(['2'])
    await userEvent.click(screen.getByRole('button', { name: 'atlas.filter_gm' }))
    expect([...pins()].map((p) => p.getAttribute('data-pin'))).toEqual(['1'])
    unmount()
    setup({ gm: true })
    await waitFor(() => expect(pins()).toHaveLength(3))
    await screen.findByRole('button', { name: 'atlas.manage' })
    expect(screen.queryByRole('button', { name: 'atlas.filter_mine' })).toBeNull()
  })

  it('hidden GM marker rendered with hidden style', async () => {
    setup({ gm: true, list: [mk(1, { visibility: 'private' }), mk(2)] })
    await waitFor(() => expect(pins()).toHaveLength(2))
    expect(document.querySelector('[data-pin="1"]')?.getAttribute('data-hidden')).toBe('true')
    expect(document.querySelector('[data-pin="2"]')?.getAttribute('data-hidden')).toBe('false')
  })

  it('back arrow with empty trail goes to state.from or campaign', async () => {
    const { unmount } = setup({ route: { pathname: '/campaign/3/atlas/9', state: { from: '/session/5' } } })
    await userEvent.click(await screen.findByRole('button', { name: 'common.back' }))
    expect(navigateSpy).toHaveBeenLastCalledWith('/session/5')
    unmount()
    const second = setup()
    await userEvent.click(await screen.findByRole('button', { name: 'common.back' }))
    expect(navigateSpy).toHaveBeenLastCalledWith('/campaign/3')
    second.unmount()
    setup({ route: { pathname: '/campaign/3/atlas/9', state: { trail: [{ id: 1, name: 'Mondo' }] } } })
    expect(await screen.findByText('Mondo')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'common.back' }))
    expect(navigateSpy).toHaveBeenLastCalledWith(-1)
  })

  it('map 404 shows unavailable state', async () => {
    maps.mockResolvedValue([])
    markers.mockRejectedValue(new ApiError(404, 'map_not_found'))
    getCampaign.mockResolvedValue({ id: 3, name: 'C', is_gm: false })
    renderWithProviders(
      <Routes><Route path="/campaign/:id/atlas/:mapId" element={<AtlasMap />} /></Routes>,
      { route: '/campaign/3/atlas/9' },
    )
    expect(await screen.findByText('atlas.unavailable')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'atlas.back_to_campaign' }))
    expect(navigateSpy).toHaveBeenCalledWith('/campaign/3')
  })

  it('deep link ?marker selects that marker', async () => {
    setup({ route: { pathname: '/campaign/3/atlas/9', search: '?marker=2' } })
    await waitFor(() => expect(document.querySelector('[data-pin="2"]')?.getAttribute('data-selected')).toBe('true'))
    expect(document.querySelector('[data-pin="1"]')?.getAttribute('data-selected')).toBe('false')
  })
})

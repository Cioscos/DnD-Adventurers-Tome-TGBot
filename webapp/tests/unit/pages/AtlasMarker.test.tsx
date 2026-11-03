import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Routes, Route } from 'react-router-dom'
import { LazyMotion, domMax } from 'framer-motion'
import { renderWithProviders } from '../utils/renderWithProviders'
import AtlasMap from '@/pages/AtlasMap'

const h = vi.hoisted(() => ({
  maps: vi.fn(), markers: vi.fn(), getCampaign: vi.fn(), navigateSpy: vi.fn(),
  createMarker: vi.fn(), updateMarker: vi.fn(), setVisibility: vi.fn(), deleteMarker: vi.fn(),
  types: vi.fn(), createType: vi.fn(), deleteType: vi.fn(),
  center: vi.fn(), centerOn: vi.fn(),
  onTransform: null as null | ((s: number) => void),
  pageBack: null as null | (() => void),
  ApiError: class ApiError extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))

vi.mock('@/api/client', () => ({
  api: {
    atlas: {
      maps: h.maps, markers: h.markers, mapImageUrl: () => 'http://x/img',
      createMarker: h.createMarker, updateMarker: h.updateMarker, setVisibility: h.setVisibility,
      deleteMarker: h.deleteMarker, types: h.types, createType: h.createType, deleteType: h.deleteType,
    },
    campaigns: { get: h.getCampaign },
  },
  ApiError: h.ApiError,
}))
// The real canvas needs layout (jsdom has none): a stub exposing the ref API and the pins as buttons.
vi.mock('@/pages/atlas/MapCanvas', async () => {
  const React = await import('react')
  return {
    default: React.forwardRef((p: { markers: { id: number; name: string }[]; onSelect: (id: number) => void; onTransform?: (s: number) => void }, ref) => {
      React.useImperativeHandle(ref, () => ({ getCenterPoint: h.center, centerOn: h.centerOn }))
      h.onTransform = p.onTransform ?? null
      return React.createElement('div', null, p.markers.map((mk) =>
        React.createElement('button', { key: mk.id, 'data-pin': mk.id, onClick: () => p.onSelect(mk.id) }, `pin ${mk.name}`)))
    }),
  }
})
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useNavigate: () => h.navigateSpy }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/hooks/useOverlayDismiss', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, usePageBack: (fn: (() => void) | null) => { h.pageBack = fn } }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))

const builtin = (key: string, icon: string, color: string) => ({ id: null, key, name: key, icon, color, builtin: true, can_delete: false })
const TYPES = [builtin('city', 'castle', 'gold'), builtin('poi', 'landmark', 'cobalt')]
const mk = (id: number, over = {}) => ({
  id, map_id: 9, name: `M${id}`, description: 'desc', x: 0.5, y: 0.5, visibility: 'public', type: TYPES[0],
  author_role: 'gm', author_name: null, mine: false, link_map_id: null, can_edit: false, can_delete: false,
  updated_at: 'x', ...over,
})
const theMap = { id: 9, name: 'Faerûn', revealed: true, revealed_at: null, updated_at: 'u', marker_count: 1 }

function setup({ gm = false, list = [mk(1)] as unknown[], maps = [theMap] as unknown[] } = {}) {
  h.maps.mockResolvedValue(maps)
  h.markers.mockResolvedValue(list)
  h.types.mockResolvedValue(TYPES)
  h.getCampaign.mockResolvedValue({ id: 3, name: 'C', is_gm: gm })
  h.center.mockReturnValue({ x: 0.25, y: 0.75 })
  return renderWithProviders(
    // As in main.tsx: without LazyMotion the Sheet backdrop (initial pointer-events:none) never becomes clickable.
    <LazyMotion features={domMax}><Routes><Route path="/campaign/:id/atlas/:mapId" element={<AtlasMap />} /></Routes></LazyMotion>,
    { route: '/campaign/3/atlas/9' },
  )
}
// Input's label is not tied to the field: take the field next to the label (an exiting sheet may still be in the DOM).
const firstField = async (label: string) =>
  ready((await screen.findByText(label)).parentElement!.querySelector('input,textarea') as HTMLElement)
/** Finds a control and waits until the sheet holding it has finished entering (clickable). */
async function ready<T extends HTMLElement>(el: T): Promise<T> {
  const sheet = el.closest('[class*="fixed"]')
  if (sheet) await waitFor(() => expect(sheet).toHaveStyle({ pointerEvents: 'auto' }))
  return el
}
const btn = async (name: string) => ready(await screen.findByRole('button', { name }))
const radio = async (name: string) => ready(await screen.findByRole('radio', { name }))
async function openSheet(name = 'M1') {
  await userEvent.click(await screen.findByText(`pin ${name}`))
}

afterEach(() => { Object.values(h).forEach((f) => typeof f === 'function' && 'mockReset' in f && (f as { mockReset(): void }).mockReset()) })

describe('Atlas markers', () => {
  it('place mode: Metti qui disabled when center is outside', async () => {
    setup()
    h.center.mockReturnValue(null)
    await userEvent.click(await btn('atlas.new_marker'))
    expect(((await btn('atlas.place_here')) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText('atlas.off_map')).toBeTruthy()
    expect(screen.getByText('atlas.place_hint')).toBeTruthy()
    h.center.mockReturnValue({ x: 0.3, y: 0.4 })
    act(() => h.onTransform?.(2))
    await waitFor(() => expect((screen.getByRole('button', { name: 'atlas.place_here' }) as HTMLButtonElement).disabled).toBe(false))
    expect(screen.queryByText('atlas.off_map')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'common.cancel' }))
    expect(screen.queryByRole('button', { name: 'atlas.place_here' })).toBeNull()
  })

  it('place then submit posts marker with x,y and default private', async () => {
    setup()
    h.createMarker.mockResolvedValue(mk(5))
    await userEvent.click(await btn('atlas.new_marker'))
    await userEvent.click(await btn('atlas.place_here'))
    await userEvent.type(await firstField('atlas.marker_name'), '  Torre  ')
    await userEvent.click(await btn('common.save'))
    await waitFor(() => expect(h.createMarker).toHaveBeenCalled())
    const [camp, map, body] = h.createMarker.mock.calls[0]
    expect([camp, map]).toEqual([3, 9])
    expect(body).toMatchObject({ name: 'Torre', x: 0.25, y: 0.75, visibility: 'private', type_key: 'poi', custom_type_id: null })
    expect(body).not.toHaveProperty('link_map_id')
    await waitFor(() => expect(h.markers).toHaveBeenCalledTimes(2))
  })

  it('GM form shows link select, player form does not', async () => {
    const { unmount } = setup({ gm: true, maps: [theMap, { ...theMap, id: 10, name: 'Vael' }] })
    await userEvent.click(await btn('atlas.new_marker'))
    await userEvent.click(await btn('atlas.place_here'))
    expect(await screen.findByText('atlas.link_label')).toBeTruthy()
    expect(screen.getByRole('radio', { name: 'atlas.vis_hidden' }).getAttribute('aria-checked')).toBe('true')
    unmount()
    setup()
    await userEvent.click(await btn('atlas.new_marker'))
    await userEvent.click(await btn('atlas.place_here'))
    await firstField('atlas.marker_name')
    expect(screen.queryByText('atlas.link_label')).toBeNull()
    expect(screen.getByRole('radio', { name: 'atlas.vis_private' }).getAttribute('aria-checked')).toBe('true')
  })

  it('player sheet shows Rendi pubblico, GM shows Rivela for hidden', async () => {
    const mine = { visibility: 'private', author_role: 'player', author_name: 'Ari', mine: true, can_edit: true, can_delete: true }
    h.setVisibility.mockResolvedValue(mk(1))
    const { unmount } = setup({ list: [mk(1, mine)] })
    await openSheet()
    expect(await screen.findByText('atlas.by_player')).toBeTruthy()
    expect(screen.getByText('atlas.vis_private')).toBeTruthy()
    await userEvent.click(await btn('atlas.make_public'))
    await waitFor(() => expect(h.setVisibility).toHaveBeenCalledWith(3, 1, 'public'))
    unmount()
    setup({ gm: true, list: [mk(1, { visibility: 'private', mine: true, can_edit: true, can_delete: true })] })
    await openSheet()
    expect(await screen.findByText('atlas.by_gm')).toBeTruthy()
    expect(screen.getByText('atlas.vis_hidden')).toBeTruthy()
    expect(await btn('atlas.reveal')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'atlas.make_public' })).toBeNull()
  })

  it('no edit/delete actions when can_edit/can_delete false', async () => {
    setup()
    await openSheet()
    expect(await screen.findByText('desc')).toBeTruthy()
    for (const name of ['common.edit', 'atlas.move', 'common.delete', 'atlas.reveal', 'atlas.hide', 'atlas.make_public', 'atlas.make_private']) {
      expect(screen.queryByRole('button', { name })).toBeNull()
    }
  })

  it('open linked map pushes trail state', async () => {
    setup({ list: [mk(1, { link_map_id: 10 })], maps: [theMap, { ...theMap, id: 10, name: 'Vael' }] })
    await openSheet()
    await userEvent.click(await btn('atlas.open_map'))
    expect(h.navigateSpy).toHaveBeenCalledWith('/campaign/3/atlas/10', { state: { trail: [{ id: 9, name: 'Faerûn' }], from: undefined } })
  })

  it('create custom type selects it in form', async () => {
    setup()
    const custom = { id: 77, key: null, name: 'Rovina', icon: 'skull', color: 'crimson', builtin: false, can_delete: true }
    h.createType.mockImplementation(async () => { h.types.mockResolvedValue([...TYPES, custom]); return custom })
    h.createMarker.mockResolvedValue(mk(5))
    await userEvent.click(await btn('atlas.new_marker'))
    await userEvent.click(await btn('atlas.place_here'))
    await userEvent.click(await btn('atlas.new_type'))
    await userEvent.type(await firstField('atlas.type_name'), 'Rovina')
    await userEvent.click(await radio('skull'))
    await userEvent.click(await radio('crimson'))
    await userEvent.click(await btn('atlas.create_type'))
    await waitFor(() => expect(h.createType).toHaveBeenCalledWith(3, { name: 'Rovina', icon: 'skull', color: 'crimson' }))
    await waitFor(() => expect(screen.getByRole('radio', { name: 'Rovina' }).getAttribute('aria-checked')).toBe('true'))
    expect(await btn('atlas.delete_type')).toBeTruthy()
    await userEvent.type((await firstField('atlas.marker_name')), 'Cripta')
    await userEvent.click(await btn('common.save'))
    await waitFor(() => expect(h.createMarker.mock.calls[0][2]).toMatchObject({ custom_type_id: 77, type_key: null }))
  })

  it('move mode saves coordinates without opening form', async () => {
    setup({ list: [mk(1, { mine: true, can_edit: true, can_delete: true })] })
    h.updateMarker.mockResolvedValue(mk(1))
    await openSheet()
    await userEvent.click(await btn('atlas.move'))
    expect(h.centerOn).toHaveBeenCalledWith({ x: 0.5, y: 0.5 })
    h.center.mockReturnValue({ x: 0.1, y: 0.2 })
    act(() => h.onTransform?.(2))
    await userEvent.click(await btn('atlas.place_here'))
    await waitFor(() => expect(h.updateMarker).toHaveBeenCalledWith(3, 1, { x: 0.1, y: 0.2 }))
    expect(screen.queryByText('atlas.marker_name')).toBeNull()
    await waitFor(() => expect(screen.queryByRole('button', { name: 'atlas.place_here' })).toBeNull())
  })

  it('Telegram back in crosshair mode cancels it instead of leaving the page', async () => {
    setup()
    await userEvent.click(await btn('atlas.new_marker'))
    await btn('atlas.place_here')
    act(() => h.pageBack?.())
    await waitFor(() => expect(screen.queryByRole('button', { name: 'atlas.place_here' })).toBeNull())
    expect(h.navigateSpy).not.toHaveBeenCalled()
    act(() => h.pageBack?.())
    expect(h.navigateSpy).toHaveBeenCalledWith('/campaign/3')
  })
})

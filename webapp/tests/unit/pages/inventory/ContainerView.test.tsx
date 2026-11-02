import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '../../utils/renderWithProviders'
import Inventory from '@/pages/Inventory'

const { getChar } = vi.hoisted(() => ({ getChar: vi.fn() }))

vi.mock('@/api/client', () => ({
  api: {
    characters: { get: getChar },
    homebrew: { listRules: vi.fn().mockResolvedValue([]) },
  },
  ApiError: class extends Error {},
}))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string, o?: { defaultValue?: string }) => o?.defaultValue ?? k, i18n: { language: 'it' } }) }
})
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/pages/inventory/InventoryItem', async () => {
  const React = await import('react')
  return { default: (p: { item: { name: string } }) => React.createElement('div', { 'data-testid': 'item' }, p.item.name) }
})
vi.mock('@/pages/inventory/AttunementSection', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'attunement' }) }
})
vi.mock('@/dice/useAnimatedRoll', () => ({ useAnimatedRoll: () => vi.fn() }))
vi.mock('@/hooks/useD20Roll', () => ({ useD20Roll: () => vi.fn(), d20Arg: vi.fn() }))
vi.mock('@/pages/spells/useItemCast', () => ({ useItemCast: () => ({ elements: null, mutate: vi.fn() }) }))
vi.mock('@/hooks/useShareMessage', () => ({ useShareMessage: () => ({ mutate: vi.fn() }) }))
vi.mock('@/auth/telegram', () => ({
  canShareMessage: () => false,
  haptic: new Proxy({}, { get: () => () => {} }),
}))

vi.stubGlobal('IntersectionObserver', class { observe() {} disconnect() {} unobserve() {} })

const meta = (extra = {}) => ({ container: { capacity_lb: 30, counts_weight: true, quick_access: false, coins: {}, ...extra } })
const base = { weight: 1, quantity: 1, is_equipped: false }
const char = {
  id: 5, carry_capacity: 100, encumbrance_total: 10, ability_scores: [],
  items: [
    { ...base, id: 1, name: 'Zaino', item_type: 'gear', container_id: null, item_metadata: meta(),
      container_stats: { contents_weight: 12, items_count: 1, containers_count: 0, over_capacity: false } },
    { ...base, id: 2, name: 'Spada', item_type: 'weapon', container_id: null },
    { ...base, id: 3, name: 'Corda', item_type: 'gear', container_id: 1 },
  ],
}

function renderAt(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/char/:id/inventory" element={<Inventory />} />
      <Route path="/char/:id/inventory/c/:containerId" element={<Inventory />} />
    </Routes>,
    { route },
  )
}

describe('Inventory a cartelle', () => {
  it('alla radice: card contenitore e solo oggetti senza container_id', async () => {
    getChar.mockResolvedValue(char)
    renderAt('/char/5/inventory')
    expect(await screen.findByText('Zaino')).toBeInTheDocument()
    expect(screen.getAllByTestId('item').map((e) => e.textContent)).toEqual(['Spada'])
    expect(screen.getByTestId('attunement')).toBeInTheDocument()
  })

  it('dentro un contenitore: figli e percorso', async () => {
    getChar.mockResolvedValue(char)
    renderAt('/char/5/inventory/c/1')
    expect(await screen.findByText('Corda')).toBeInTheDocument()
    expect(screen.getAllByTestId('item').map((e) => e.textContent)).toEqual(['Corda'])
    expect(screen.getByLabelText('breadcrumb')).toHaveTextContent(/containers.root.*Zaino/)
    expect(screen.queryByTestId('attunement')).toBeNull()
  })

  it('contenitore inesistente: redirect alla radice', async () => {
    getChar.mockResolvedValue(char)
    renderAt('/char/5/inventory/c/99')
    expect(await screen.findByText('Spada')).toBeInTheDocument()
  })
})

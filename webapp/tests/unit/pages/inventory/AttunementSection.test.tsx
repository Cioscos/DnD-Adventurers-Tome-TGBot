import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AttunementSection from '@/pages/inventory/AttunementSection'
import type { Item } from '@/types'

const { update } = vi.hoisted(() => ({ update: vi.fn() }))
vi.mock('@/api/client', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, api: { items: { update } } }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: vi.fn(), success: vi.fn() }) }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return {
    ...actual,
    useTranslation: () => ({ t: (k: string, o?: { n?: number }) => (o?.n != null ? `${k}:${o.n}` : k), i18n: { language: 'it' } }),
  }
})

const mk = (id: number, attuned: boolean): Item => ({
  id, name: `Anello ${id}`, item_type: 'accessory', quantity: 1, weight: 0, is_equipped: false,
  item_metadata: { requires_attunement: true, attuned, hb_x: 1 },
} as unknown as Item)

function renderIt(items: Item[]) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
      <AttunementSection charId={7} items={items} />
    </QueryClientProvider>,
  )
}

afterEach(() => vi.clearAllMocks())

describe('AttunementSection', () => {
  it('shows 3 slots, filled by attuned items', () => {
    renderIt([mk(1, true), mk(2, false)])
    expect(screen.getAllByTestId('attunement-slot')).toHaveLength(3)
    expect(screen.getAllByText('Anello 1').length).toBeGreaterThan(0)
    expect(screen.getAllByTestId('attunement-slot-empty')).toHaveLength(2)
  })

  it('attunes by sending the merged metadata', async () => {
    update.mockResolvedValue({})
    renderIt([mk(2, false)])
    await userEvent.click(screen.getByRole('button', { name: /Anello 2/ }))
    await waitFor(() => expect(update).toHaveBeenCalledWith(7, 2, {
      item_metadata: { requires_attunement: true, attuned: true, hb_x: 1 },
    }))
  })

  it('shows the limit message on a 409', async () => {
    const { ApiError } = await import('@/api/client')
    update.mockRejectedValue(new ApiError(409, 'attunement_limit'))
    renderIt([mk(1, true), mk(2, true), mk(3, true), mk(4, false)])
    await userEvent.click(screen.getByRole('button', { name: /Anello 4/ }))
    expect(await screen.findByText('character.inventory.magic.attunement_limit')).toBeTruthy()
  })
})

describe('AttunementSection other 409s', () => {
  it('does not claim the limit for a different 409', async () => {
    const { ApiError } = await import('@/api/client')
    update.mockRejectedValue(new ApiError(409, 'something_else'))
    renderIt([mk(4, false)])
    await userEvent.click(screen.getByRole('button', { name: /Anello 4/ }))
    expect(await screen.findByRole('alert')).toBeTruthy()
    expect(screen.queryByText('character.inventory.magic.attunement_limit')).toBeNull()
  })
})

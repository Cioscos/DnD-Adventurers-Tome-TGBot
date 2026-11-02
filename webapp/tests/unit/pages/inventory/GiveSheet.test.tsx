import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient } from '@tanstack/react-query'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import { renderWithProviders } from '../../utils/renderWithProviders'
import GiveSheet from '@/pages/inventory/GiveSheet'
import type { Item, SessionParticipant } from '@/types'

const { trade, toastInfo } = vi.hoisted(() => ({ trade: vi.fn(), toastInfo: vi.fn() }))
vi.mock('@/api/client', () => ({
  api: { sessions: { trade } },
  ApiError: class extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ info: toastInfo, error: vi.fn(), success: vi.fn() }) }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string, o?: Record<string, unknown>) => (o ? `${k}|${JSON.stringify(o)}` : k), i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})

const partners: SessionParticipant[] = [
  { user_id: 2, role: 'player', character_id: 20, display_name: 'Aldo', character_name: 'Thorin', joined_at: '' },
  { user_id: 3, role: 'player', character_id: 30, display_name: null, joined_at: '' },
]
const it_ = (id: number, name: string, over: Record<string, unknown> = {}) =>
  ({ id, name, item_type: 'gear', quantity: 1, weight: 1, is_equipped: false, container_id: null, ...over }) as unknown as Item
const box = (id: number, name: string, parent: number | null, coins = {}) =>
  it_(id, name, { container_id: parent, item_metadata: { container: { capacity_lb: null, counts_weight: true, quick_access: false, coins } } })

beforeEach(() => { trade.mockReset(); toastInfo.mockReset() })

function setup(item: Item, items: Item[]) {
  const onClose = vi.fn()
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  renderWithProviders(
    <GiveSheet charId={10} sessionId={9} partners={partners} item={item} items={items} onClose={onClose} />,
    { client: qc },
  )
  return { onClose, qc }
}

describe('GiveSheet', () => {
  it('elenca i compagni per display_name (fallback #user_id)', () => {
    const f = it_(1, 'Corda')
    setup(f, [f])
    expect(screen.getByRole('button', { name: /Thorin.*Aldo/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /#3/ })).toBeInTheDocument()
  })

  it('contenitore in pila: niente stepper, si dà intero', () => {
    const z = box(1, 'Zaino', null)
    setup({ ...z, quantity: 2 } as Item, [z])
    expect(screen.queryByLabelText('character.inventory.containers.qty_minus')).toBeNull()
  })

  it('pila x20: stepper 1..20, default 20, quantity omessa se intera', async () => {
    const f = it_(1, 'Frecce', { quantity: 20 })
    trade.mockResolvedValue({ id: 10, items: [] })
    const { onClose } = setup(f, [f])
    expect(screen.getByText('20 / 20')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Thorin/ }))
    fireEvent.click(screen.getByRole('button', { name: 'character.inventory.give.confirm' }))
    await waitFor(() => expect(onClose).toHaveBeenCalled())
    expect(trade).toHaveBeenCalledWith(9, { from_character_id: 10, to_user_id: 2, item_id: 1 })
  })

  it('quantità parziale inviata', async () => {
    const f = it_(1, 'Frecce', { quantity: 20 })
    trade.mockResolvedValue({ id: 10, items: [] })
    setup(f, [f])
    fireEvent.click(screen.getByLabelText('character.inventory.containers.qty_minus'))
    fireEvent.click(screen.getByRole('button', { name: /Thorin/ }))
    fireEvent.click(screen.getByRole('button', { name: 'character.inventory.give.confirm' }))
    await waitFor(() => expect(trade).toHaveBeenCalled())
    expect(trade).toHaveBeenCalledWith(9, { from_character_id: 10, to_user_id: 2, item_id: 1, quantity: 19 })
  })

  it('contenitore: riepilogo con oggetti discendenti e monete', () => {
    const z = box(1, 'Zaino', null, { gold: 5 })
    const t_ = box(2, 'Tasca', 1, { gold: 7, silver: 3 })
    const items = [z, t_, it_(3, 'Corda', { container_id: 1 }), it_(4, 'Chiave', { container_id: 2 })]
    setup(z, items)
    const s = screen.getByTestId('give-summary').textContent!
    expect(s).toContain('"count":3')
    expect(s).toContain('12 GP')
    expect(s).toContain('3 SP')
  })

  it('al successo aggiorna la cache, avvisa dei disequipaggiati e chiude', async () => {
    const f = it_(1, 'Spada')
    trade.mockResolvedValue({ id: 10, items: [], unequipped_item_names: ['Spada'] })
    const { onClose, qc } = setup(f, [f])
    fireEvent.click(screen.getByRole('button', { name: /Thorin/ }))
    fireEvent.click(screen.getByRole('button', { name: 'character.inventory.give.confirm' }))
    await waitFor(() => expect(onClose).toHaveBeenCalled())
    expect(qc.getQueryData(['character', 10])).toMatchObject({ id: 10 })
    expect(toastInfo).toHaveBeenCalled()
  })
})

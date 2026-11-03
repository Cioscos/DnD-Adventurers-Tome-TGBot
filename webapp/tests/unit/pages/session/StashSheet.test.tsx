import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient } from '@tanstack/react-query'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import { renderWithProviders } from '../../utils/renderWithProviders'
import StashSheet from '@/pages/session/StashSheet'
import itLocale from '@/locales/it.json'
import type { Item } from '@/types'

const m = vi.hoisted(() => ({ stash: vi.fn(), stashTake: vi.fn(), stashGmAdd: vi.fn(), stashGmRemove: vi.fn() }))
vi.mock('@/api/client', () => ({
  api: { sessions: { stash: m.stash, stashTake: m.stashTake, stashGmAdd: m.stashGmAdd, stashGmRemove: m.stashGmRemove } },
  ApiError: class extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ info: vi.fn(), error: vi.fn(), success: vi.fn() }) }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
// ItemForm è pesante: basta sapere che GrantItemModal in modalità deposito lo usa e ne inoltra i dati.
vi.mock('@/pages/inventory/ItemForm', async () => {
  const React = await import('react')
  return {
    default: (p: { onSubmit: (d: unknown) => void }) =>
      React.createElement('button', { onClick: () => p.onSubmit({ name: 'Pozione', description: '', weight: '1', quantity: '2', item_type: 'consumable' }) }, 'form-submit'),
  }
})
vi.mock('@/pages/inventory/itemMetadata', () => ({ buildItemMetadata: () => ({}) }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  const t = (k: string, o?: Record<string, string>) => {
    const raw = k.split('.').reduce<unknown>((a, p) => (a as Record<string, unknown> | undefined)?.[p], itLocale) as string | undefined
    return (raw ?? k).replace(/\{\{(\w+)\}\}/g, (_, n) => String(o?.[n] ?? ''))
  }
  return { ...actual, useTranslation: () => ({ t, i18n: { language: 'it' } }) }
})

const it_ = (id: number, name: string, over: Record<string, unknown> = {}) =>
  ({ id, name, item_type: 'gear', quantity: 1, weight: 1, is_equipped: false, container_id: null, ...over }) as unknown as Item
const stash = {
  items: [
    it_(1, 'Frecce', { quantity: 20 }),
    it_(2, 'Zaino', { item_metadata: { container: { capacity_lb: null, counts_weight: true, quick_access: false, coins: {} } } }),
  ],
  currency: { id: 1, copper: 0, silver: 0, electrum: 0, gold: 50, platinum: 0 },
}
const minus = itLocale.character.inventory.containers.qty_minus
// L'etichetta di Input non è collegata al campo: si risale dal testo.
const goldInput = () => screen.getByText(/^Oro/).parentElement!.querySelector('input')!
const last = (name: string) => screen.getAllByRole('button', { name }).at(-1)!

function setup(isGm: boolean, myCharId: number | null = 14, data: typeof stash = stash) {
  m.stash.mockResolvedValue(data)
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const inv = vi.spyOn(qc, 'invalidateQueries')
  renderWithProviders(<StashSheet sessionId={5} isGm={isGm} myCharId={myCharId} participants={[]} gmUserId={1} onClose={vi.fn()} />, { client: qc })
  return { qc, inv }
}

beforeEach(() => Object.values(m).forEach((f) => f.mockReset()))

describe('StashSheet giocatore', () => {
  it('Prendi su una pila: stepper, poi stash/take con quantità e cache PG', async () => {
    m.stashTake.mockResolvedValue({ id: 14, items: [] })
    const { qc, inv } = setup(false)
    await screen.findByText(/Frecce/)
    fireEvent.click(screen.getAllByRole('button', { name: 'Prendi' })[1]) // [0] = cassa
    expect(screen.getByText('20 / 20')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText(minus))
    fireEvent.click(last('Prendi'))
    await waitFor(() => expect(m.stashTake).toHaveBeenCalledWith(5, { to_character_id: 14, item_id: 1, quantity: 19 }))
    await waitFor(() => expect(qc.getQueryData(['character', 14])).toMatchObject({ id: 14 }))
    expect(inv).toHaveBeenCalledWith({ queryKey: ['session-stash', 5] })
  })

  it('Prendi un contenitore: nessuno stepper, si prende intero', async () => {
    m.stashTake.mockResolvedValue({ id: 14, items: [] })
    setup(false)
    await screen.findByText(/Zaino/)
    fireEvent.click(screen.getAllByRole('button', { name: 'Prendi' })[2])
    expect(screen.queryByLabelText(minus)).toBeNull()
    fireEvent.click(last('Prendi'))
    await waitFor(() => expect(m.stashTake).toHaveBeenCalledWith(5, { to_character_id: 14, item_id: 2 }))
  })

  it('cassa: oltre il disponibile blocca la conferma, altrimenti stash/take coins', async () => {
    m.stashTake.mockResolvedValue({ id: 14, items: [] })
    setup(false)
    await screen.findByText(/Frecce/)
    fireEvent.click(screen.getAllByRole('button', { name: 'Prendi' })[0])
    const gold = goldInput()
    fireEvent.change(gold, { target: { value: '51' } })
    expect(last('Prendi')).toBeDisabled()
    fireEvent.change(gold, { target: { value: '30' } })
    fireEvent.click(last('Prendi'))
    await waitFor(() => expect(m.stashTake).toHaveBeenCalledWith(5, { to_character_id: 14, coins: { gold: 30 } }))
  })

  it('niente azioni da master per i giocatori', async () => {
    setup(false)
    await screen.findByText(/Frecce/)
    expect(screen.queryByRole('button', { name: 'Metti nel deposito' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Togli' })).toBeNull()
  })
})

describe('StashSheet cassa', () => {
  it('cassa vuota: niente Prendi/Togli sulla riga monete', async () => {
    const empty = { ...stash, currency: { ...stash.currency, gold: 0 } }
    setup(false, 14, empty)
    await screen.findByText(/Frecce/)
    expect(screen.getAllByRole('button', { name: 'Prendi' })).toHaveLength(2) // solo le due righe oggetto
    expect(m.stash).toHaveBeenCalled()
  })

  it('prendi/togli elenca solo le monete presenti, con migliaia formattate', async () => {
    const rich = { ...stash, currency: { ...stash.currency, gold: 12400, silver: 85 } }
    setup(false, 14, rich)
    await screen.findByText(/Frecce/)
    fireEvent.click(screen.getAllByRole('button', { name: 'Prendi' })[0])
    expect(screen.getByText(/^Oro \(12\.400\)/)).toBeInTheDocument()
    expect(screen.getByText(/^Argento \(85\)/)).toBeInTheDocument()
    expect(screen.queryByText(/^Rame/)).toBeNull()
    expect(screen.queryByText(/^Platino/)).toBeNull()
  })
})

describe('StashSheet master', () => {
  it('Metti nel deposito: form oggetto → gm-add e invalida', async () => {
    m.stashGmAdd.mockResolvedValue(stash)
    const { inv } = setup(true, null)
    await screen.findByText(/Frecce/)
    expect(screen.queryByRole('button', { name: 'Prendi' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Metti nel deposito' }))
    fireEvent.click(screen.getByText('form-submit'))
    await waitFor(() => expect(m.stashGmAdd).toHaveBeenCalled())
    expect(m.stashGmAdd.mock.calls[0][0]).toBe(5)
    expect(m.stashGmAdd.mock.calls[0][1].item).toMatchObject({ name: 'Pozione', quantity: 2 })
    await waitFor(() => expect(inv).toHaveBeenCalledWith({ queryKey: ['session-stash', 5] }))
  })

  it('Metti monete nel deposito → gm-add coins', async () => {
    m.stashGmAdd.mockResolvedValue(stash)
    setup(true, null)
    await screen.findByText(/Frecce/)
    fireEvent.click(screen.getByRole('button', { name: 'Metti monete nel deposito' }))
    fireEvent.change(goldInput(), { target: { value: '9' } })
    fireEvent.click(last('Metti nel deposito'))
    await waitFor(() => expect(m.stashGmAdd).toHaveBeenCalledWith(5, { coins: { gold: 9 } }))
  })

  it('Togli su una pila con stepper → gm-remove', async () => {
    m.stashGmRemove.mockResolvedValue(stash)
    setup(true, null)
    await screen.findByText(/Frecce/)
    fireEvent.click(screen.getAllByRole('button', { name: 'Togli' })[1])
    fireEvent.click(screen.getByLabelText(minus))
    fireEvent.click(last('Togli'))
    await waitFor(() => expect(m.stashGmRemove).toHaveBeenCalledWith(5, { item_id: 1, quantity: 19 }))
  })

  it('Togli dalla cassa → gm-remove coins', async () => {
    m.stashGmRemove.mockResolvedValue(stash)
    setup(true, null)
    await screen.findByText(/Frecce/)
    fireEvent.click(screen.getAllByRole('button', { name: 'Togli' })[0])
    fireEvent.change(goldInput(), { target: { value: '5' } })
    fireEvent.click(last('Togli'))
    await waitFor(() => expect(m.stashGmRemove).toHaveBeenCalledWith(5, { coins: { gold: 5 } }))
  })
})

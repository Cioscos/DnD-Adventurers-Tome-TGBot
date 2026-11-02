import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Currency from '@/pages/Currency'

const { getChar, adjustSpy, moveSpy, convertSpy, undoSpy } = vi.hoisted(() => ({
  getChar: vi.fn(),
  adjustSpy: vi.fn(),
  moveSpy: vi.fn(),
  convertSpy: vi.fn(),
  undoSpy: vi.fn(),
}))

vi.mock('@/components/ui/UndoToast', () => ({ showUndoToast: undoSpy }))

vi.mock('@/api/client', () => ({
  api: {
    characters: { get: getChar },
    currency: { adjust: adjustSpy, move: moveSpy, convert: convertSpy },
  },
}))

vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '5' }) }
})

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

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

vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/styles/motion', () => ({ spring: new Proxy({}, { get: () => ({}) }) }))

const passthrough = vi.hoisted(() => async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/Layout', passthrough)
vi.mock('@/components/ui/Surface', passthrough)
vi.mock('@/components/skeletons/CurrencySkeleton', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'currency-skeleton' }) }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return {
    default: (p: { onClick?: () => void; disabled?: boolean; children?: unknown; 'aria-label'?: string }) =>
      React.createElement('button', { onClick: p.onClick, disabled: p.disabled, 'aria-label': p['aria-label'] }, p.children),
  }
})
vi.mock('@/components/ui/Input', async () => {
  const React = await import('react')
  return {
    default: (p: { value: string; placeholder?: string; disabled?: boolean; type?: string; onChange: (v: string) => void }) =>
      React.createElement('input', {
        value: p.value,
        placeholder: p.placeholder,
        disabled: p.disabled,
        type: p.type,
        onChange: (e: { target: { value: string } }) => p.onChange(e.target.value),
      }),
  }
})
// Sheet renders its children only while open (so the convert form is addressable).
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return {
    default: (p: { open?: boolean; children?: unknown }) =>
      p.open ? React.createElement('div', { 'data-testid': 'sheet' }, p.children) : null,
  }
})

// Totale = borsa 4 + Zaino 6 oro: la pagina lavora sul totale, non sulla sola borsa.
const makeChar = () => ({
  id: 5,
  settings: {},
  currency: { id: 1, platinum: 0, gold: 4, electrum: 0, silver: 0, copper: 0 },
  coin_totals: { platinum: 0, gold: 10, electrum: 0, silver: 0, copper: 0 },
  coin_breakdown: [
    { container_id: null, name: null, coins: { gold: 4 } },
    { container_id: 7, name: 'Zaino', coins: { gold: 6 } },
  ],
  items: [{ id: 7, name: 'Zaino', container_id: null, item_metadata: { container: { coins: {} } } }],
})
let server = makeChar()

afterEach(() => {
  getChar.mockReset()
  adjustSpy.mockReset()
  moveSpy.mockReset()
  convertSpy.mockReset()
  undoSpy.mockReset()
})

const key = (k: string) => screen.getByRole('button', { name: k })
const amount = () => screen.getByTestId('tx-amount')

async function loaded(char: Record<string, unknown> = makeChar()) {
  server = char as ReturnType<typeof makeChar>
  getChar.mockImplementation(async () => structuredClone(server))
  // Il server finto applica il delta e risponde con i piazzamenti effettivi (firmati).
  adjustSpy.mockImplementation(async (_id: number, b: { coin: 'gold'; delta: number; placements?: { container_id: number | null; amount: number }[] }) => {
    server.coin_totals = { ...server.coin_totals, [b.coin]: server.coin_totals[b.coin] + b.delta }
    return { coin_totals: server.coin_totals, purse: {}, placements: b.placements ?? [{ container_id: null, amount: b.delta }] }
  })
  renderWithProviders(<Currency />)
  await screen.findByText('10.00')
}

describe('Currency page — totale + transazione', () => {
  it('shows the skeleton while the character query is pending', () => {
    getChar.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<Currency />)
    expect(screen.getByTestId('currency-skeleton')).toBeInTheDocument()
  })

  it('mostra monete e totale in oro dal totale (borsa + contenitori)', async () => {
    await loaded()
    expect(key('character.currency.gold: 10')).toBeInTheDocument()
  })

  it('Spendi chiama adjust con delta negativo e mostra Annulla', async () => {
    await loaded()
    await userEvent.click(key('5'))
    expect(amount()).toHaveTextContent('5')
    await userEvent.click(key('character.currency.spend'))
    await waitFor(() => expect(adjustSpy).toHaveBeenCalledWith(5, { coin: 'gold', delta: -5 }))
    expect(await screen.findByText('5.00')).toBeInTheDocument()
    await waitFor(() => expect(undoSpy).toHaveBeenCalledTimes(1))
    expect(undoSpy.mock.calls[0][0].message).toBe('character.currency.spent_toast')
  })

  it('Annulla invia i piazzamenti effettivi negati, non una nuova ripartizione', async () => {
    await loaded()
    adjustSpy.mockResolvedValueOnce({
      coin_totals: { ...server.coin_totals, gold: 5 }, purse: {},
      placements: [{ container_id: null, amount: -2 }, { container_id: 7, amount: -3 }],
    })
    await userEvent.click(key('5'))
    await userEvent.click(key('character.currency.spend'))
    await waitFor(() => expect(undoSpy).toHaveBeenCalledTimes(1))
    undoSpy.mock.calls[0][0].onUndo()
    await waitFor(() => expect(adjustSpy).toHaveBeenLastCalledWith(5, {
      coin: 'gold', delta: 5, placements: [{ container_id: null, amount: 2 }, { container_id: 7, amount: 3 }],
    }))
    expect(undoSpy).toHaveBeenCalledTimes(1) // l'annullamento non è a sua volta annullabile
  })

  it('l’avviso dice da dove sono uscite le monete solo se più di un posto', async () => {
    await loaded()
    adjustSpy.mockResolvedValueOnce({
      coin_totals: { ...server.coin_totals, gold: 5 }, purse: {},
      placements: [{ container_id: null, amount: -2 }, { container_id: 7, amount: -3 }],
    })
    await userEvent.click(key('5'))
    await userEvent.click(key('character.currency.spend'))
    await waitFor(() => expect(undoSpy).toHaveBeenCalledTimes(1))
    expect(undoSpy.mock.calls[0][0].message).toBe('character.currency.spent_from')
  })

  it('più spese in volo: ogni tocco ha il suo Annulla coi propri piazzamenti', async () => {
    await loaded()
    const gates: ((v: unknown) => void)[] = []
    adjustSpy.mockImplementation(() => new Promise((res) => { gates.push(res) }))
    await userEvent.click(key('1'))
    await userEvent.click(key('character.currency.spend'))
    await userEvent.click(key('2'))
    await userEvent.click(key('character.currency.spend'))
    await userEvent.click(key('3'))
    await userEvent.click(key('character.currency.spend'))
    await waitFor(() => expect(gates.length).toBeGreaterThan(0))
    // Le risposte arrivano in ordine (scope seriale): sblocco una alla volta.
    const amounts = [1, 2, 3]
    for (let i = 0; i < 3; i++) {
      await waitFor(() => expect(gates.length).toBe(i + 1))
      gates[i]({ coin_totals: server.coin_totals, purse: {}, placements: [{ container_id: 7, amount: -amounts[i] }] })
    }
    await waitFor(() => expect(undoSpy).toHaveBeenCalledTimes(3))
    adjustSpy.mockReset()
    adjustSpy.mockResolvedValue({ coin_totals: server.coin_totals, purse: {}, placements: [] })
    undoSpy.mock.calls[0][0].onUndo()
    await waitFor(() => expect(adjustSpy).toHaveBeenLastCalledWith(5, {
      coin: 'gold', delta: 1, placements: [{ container_id: 7, amount: 1 }],
    }))
    undoSpy.mock.calls[1][0].onUndo()
    await waitFor(() => expect(adjustSpy).toHaveBeenLastCalledWith(5, {
      coin: 'gold', delta: 2, placements: [{ container_id: 7, amount: 2 }],
    }))
  })

  it('Ricevi aggiunge sulla moneta scelta (cambio moneta coi chip)', async () => {
    await loaded()
    await userEvent.click(key('SP'))
    await userEvent.click(key('1'))
    await userEvent.click(key('2'))
    await userEvent.click(key('character.currency.receive'))
    await waitFor(() => expect(adjustSpy).toHaveBeenCalledWith(5, { coin: 'silver', delta: 12 }))
  })

  it('Spendi è disattivato se il totale non basta, e lo dice', async () => {
    await loaded()
    await userEvent.click(key('2'))
    await userEvent.click(key('0'))
    expect(key('character.currency.spend')).toBeDisabled()
    expect(screen.getByText('character.currency.not_enough')).toBeInTheDocument()
  })

  it('dopo una transazione la cifra resta, e la prossima cifra la sostituisce', async () => {
    await loaded()
    await userEvent.click(key('3'))
    await userEvent.click(key('character.currency.receive'))
    await waitFor(() => expect(adjustSpy).toHaveBeenCalledTimes(1))
    expect(amount()).toHaveTextContent('3')
    await userEvent.click(key('SP'))
    await userEvent.click(key('character.currency.receive'))
    await waitFor(() => expect(adjustSpy).toHaveBeenLastCalledWith(5, { coin: 'silver', delta: 3 }))
    await userEvent.click(key('7'))
    expect(amount()).toHaveTextContent('7')
  })

  it('cancella cifra e importo zero disattivano le azioni', async () => {
    await loaded()
    await userEvent.click(key('4'))
    await userEvent.click(key('character.currency.backspace'))
    expect(amount()).toHaveTextContent('0')
    expect(key('character.currency.receive')).toBeDisabled()
  })

  it('toccare una moneta mostra la suddivisione per posto', async () => {
    await loaded()
    await userEvent.click(key('character.currency.gold: 10'))
    const sheet = await screen.findByTestId('sheet')
    expect(within(sheet).getByText('Zaino')).toBeInTheDocument()
    expect(within(sheet).getByText('character.currency.purse')).toBeInTheDocument()
  })

  it('valore esatto: adjust con delta = valore − totale, senza placements', async () => {
    await loaded()
    await userEvent.click(key('character.currency.gold: 10'))
    await userEvent.click(within(await screen.findByTestId('sheet')).getByRole('button', { name: 'character.currency.set_exact' }))
    const sheet = await screen.findByTestId('sheet')
    const input = within(sheet).getByPlaceholderText('10')
    expect(input).toHaveValue(null)
    fireEvent.change(input, { target: { value: '7' } })
    await userEvent.click(within(sheet).getByRole('button', { name: 'common.save' }))
    await waitFor(() => expect(adjustSpy).toHaveBeenCalledWith(5, { coin: 'gold', delta: -3 }))
    await waitFor(() => expect(undoSpy).toHaveBeenCalledTimes(1))
  })

  it('Annulla del valore esatto annulla solo quel cambio, non le operazioni fatte dopo', async () => {
    await loaded()
    await userEvent.click(key('character.currency.gold: 10'))
    await userEvent.click(within(await screen.findByTestId('sheet')).getByRole('button', { name: 'character.currency.set_exact' }))
    fireEvent.change(within(await screen.findByTestId('sheet')).getByPlaceholderText('10'), { target: { value: '50' } })
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    await waitFor(() => expect(adjustSpy).toHaveBeenCalledWith(5, { coin: 'gold', delta: 40 }))
    await waitFor(() => expect(undoSpy).toHaveBeenCalledTimes(1))
    await userEvent.click(key('5'))
    await userEvent.click(key('character.currency.receive'))
    await waitFor(() => expect(adjustSpy).toHaveBeenLastCalledWith(5, { coin: 'gold', delta: 5 }))
    undoSpy.mock.calls[0][0].onUndo()
    await waitFor(() => expect(adjustSpy).toHaveBeenLastCalledWith(5, {
      coin: 'gold', delta: -40, placements: [{ container_id: null, amount: -40 }],
    }))
  })

  it('nasconde l’electrum se disattivato nelle impostazioni', async () => {
    await loaded({ ...makeChar(), settings: { hide_electrum: true } })
    expect(screen.queryByRole('button', { name: 'EP' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'character.currency.electrum: 0' })).not.toBeInTheDocument()
  })

  it('Sposta monete: move con moneta, quantità, da e a', async () => {
    await loaded()
    moveSpy.mockResolvedValue({ coin_totals: server.coin_totals, purse: {}, placements: [] })
    await userEvent.click(key('character.currency.gold: 10'))
    await userEvent.click(within(await screen.findByTestId('sheet')).getByRole('button', { name: 'character.currency.move' }))
    const sheet = await screen.findByTestId('sheet')
    // Da = borsa (prima con monete), A = Zaino.
    await userEvent.click(within(sheet).getByRole('button', { name: 'Zaino' }))
    fireEvent.change(within(sheet).getByPlaceholderText('0'), { target: { value: '3' } })
    await userEvent.click(within(sheet).getByRole('button', { name: 'character.currency.move_confirm' }))
    await waitFor(() => expect(moveSpy).toHaveBeenCalledWith(5, {
      coin: 'gold', amount: 3, from_container_id: null, to_container_id: 7,
    }))
  })

  it('convert posts (source, target, amount) and refreshes the character', async () => {
    await loaded()
    convertSpy.mockResolvedValue({})
    await userEvent.click(screen.getByRole('button', { name: 'character.currency.convert' }))
    const sheet = await screen.findByTestId('sheet')
    fireEvent.change(within(sheet).getByPlaceholderText('0'), { target: { value: '2' } })
    const calls = getChar.mock.calls.length
    await userEvent.click(within(sheet).getByRole('button', { name: 'character.currency.convert' }))
    await waitFor(() => expect(convertSpy).toHaveBeenCalledWith(5, 'gold', 'silver', 2))
    await waitFor(() => expect(getChar.mock.calls.length).toBeGreaterThan(calls))
  })
})

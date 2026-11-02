import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Currency from '@/pages/Currency'

const { getChar, updateSpy, convertSpy, undoSpy } = vi.hoisted(() => ({
  getChar: vi.fn(),
  updateSpy: vi.fn(),
  convertSpy: vi.fn(),
  undoSpy: vi.fn(),
}))

vi.mock('@/components/ui/UndoToast', () => ({ showUndoToast: undoSpy }))

vi.mock('@/api/client', () => ({
  api: {
    characters: { get: getChar },
    currency: { update: updateSpy, convert: convertSpy },
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

// CurrencyRead-shaped fixture (the exact BE serializer shape — id + 5 coin ints).
// Keeping a single non-zero coin makes the total-gold assertion exact.
const baseChar = {
  id: 5,
  settings: {},
  currency: { id: 1, platinum: 0, gold: 10, electrum: 0, silver: 0, copper: 0 },
}

afterEach(() => {
  getChar.mockReset()
  updateSpy.mockReset()
  convertSpy.mockReset()
  undoSpy.mockReset()
})

const key = (k: string) => screen.getByRole('button', { name: k })
const amount = () => screen.getByTestId('tx-amount')

async function loaded(char: unknown = baseChar) {
  getChar.mockResolvedValue(char)
  updateSpy.mockImplementation(async (_id: number, data: Record<string, number>) => ({ ...baseChar.currency, ...data }))
  renderWithProviders(<Currency />)
  await screen.findByText('10.00')
}

describe('Currency page — borsa + transazione', () => {
  it('shows the skeleton while the character query is pending', () => {
    getChar.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<Currency />)
    expect(screen.getByTestId('currency-skeleton')).toBeInTheDocument()
  })

  it('mostra il totale in oro e le monete della borsa (read contract)', async () => {
    await loaded()
    expect(key('character.currency.gold: 10')).toBeInTheDocument()
  })

  it('Spendi toglie l’importo dalla moneta scelta e salva subito, con Annulla', async () => {
    await loaded()
    await userEvent.click(key('5'))
    expect(amount()).toHaveTextContent('5')
    await userEvent.click(key('character.currency.spend'))
    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith(5, { gold: 5 }))
    expect(await screen.findByText('5.00')).toBeInTheDocument()
    expect(undoSpy).toHaveBeenCalledTimes(1)

    // Annulla = operazione inversa sul valore corrente (non ripristina una foto vecchia).
    undoSpy.mock.calls[0][0].onUndo()
    await waitFor(() => expect(updateSpy).toHaveBeenLastCalledWith(5, { gold: 10 }))
  })

  it('Ricevi aggiunge sulla moneta scelta (cambio moneta coi chip)', async () => {
    await loaded()
    await userEvent.click(key('SP'))
    await userEvent.click(key('1'))
    await userEvent.click(key('2'))
    await userEvent.click(key('character.currency.receive'))
    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith(5, { silver: 12 }))
  })

  it('Spendi è disattivato se la moneta non basta, e lo dice', async () => {
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
    await waitFor(() => expect(updateSpy).toHaveBeenCalledTimes(1))
    expect(amount()).toHaveTextContent('3')
    // Cifra mista: cambio moneta e ripremo, senza riscrivere.
    await userEvent.click(key('SP'))
    await userEvent.click(key('character.currency.receive'))
    await waitFor(() => expect(updateSpy).toHaveBeenLastCalledWith(5, { silver: 3 }))
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

  it('toccare una moneta della borsa apre il valore esatto: campo vuoto col valore attuale suggerito', async () => {
    await loaded()
    await userEvent.click(key('character.currency.gold: 10'))
    const sheet = await screen.findByTestId('sheet')
    const input = within(sheet).getByPlaceholderText('10')
    expect(input).toHaveValue(null) // campo numerico vuoto
    fireEvent.change(input, { target: { value: '7' } })
    await userEvent.click(within(sheet).getByRole('button', { name: 'common.save' }))
    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith(5, { gold: 7 }))
    expect(undoSpy).toHaveBeenCalledTimes(1)
  })

  it('Annulla del valore esatto annulla solo quel cambio, non le operazioni fatte dopo', async () => {
    await loaded()
    await userEvent.click(key('character.currency.gold: 10'))
    fireEvent.change(within(await screen.findByTestId('sheet')).getByPlaceholderText('10'), { target: { value: '50' } })
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith(5, { gold: 50 }))
    await userEvent.click(key('5'))
    await userEvent.click(key('character.currency.receive'))
    await waitFor(() => expect(updateSpy).toHaveBeenLastCalledWith(5, { gold: 55 }))
    undoSpy.mock.calls[0][0].onUndo()
    await waitFor(() => expect(updateSpy).toHaveBeenLastCalledWith(5, { gold: 15 }))
  })

  it('nasconde l’electrum se disattivato nelle impostazioni', async () => {
    await loaded({ ...baseChar, settings: { hide_electrum: true } })
    expect(screen.queryByRole('button', { name: 'EP' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'character.currency.electrum: 0' })).not.toBeInTheDocument()
  })

  it('convert posts (source, target, amount) to the convert endpoint', async () => {
    await loaded()
    convertSpy.mockResolvedValue(baseChar.currency)
    await userEvent.click(screen.getByRole('button', { name: 'character.currency.convert' }))
    const sheet = await screen.findByTestId('sheet')
    fireEvent.change(within(sheet).getByPlaceholderText('0'), { target: { value: '2' } })
    await userEvent.click(within(sheet).getByRole('button', { name: 'character.currency.convert' }))
    await waitFor(() => expect(convertSpy).toHaveBeenCalledWith(5, 'gold', 'silver', 2))
  })
})

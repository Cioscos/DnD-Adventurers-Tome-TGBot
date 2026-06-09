import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Currency from '@/pages/Currency'

const { getChar, updateSpy, convertSpy } = vi.hoisted(() => ({
  getChar: vi.fn(),
  updateSpy: vi.fn(),
  convertSpy: vi.fn(),
}))

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

vi.mock('@/auth/telegram', () => ({ haptic: { success: () => {}, error: () => {} } }))
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
    default: (p: { onClick?: () => void; disabled?: boolean; children?: unknown }) =>
      React.createElement('button', { onClick: p.onClick, disabled: p.disabled }, p.children),
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
})

describe('Currency page', () => {
  it('shows the skeleton while the character query is pending', () => {
    getChar.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<Currency />)
    expect(screen.getByTestId('currency-skeleton')).toBeInTheDocument()
  })

  it('renders the total-gold value from the CurrencyRead shape (read contract)', async () => {
    getChar.mockResolvedValue(baseChar)
    renderWithProviders(<Currency />)
    // 0 pp + 10 gp + 0 ep + 0 sp + 0 cp = 10.00 gp
    expect(await screen.findByText('10.00')).toBeInTheDocument()
  })

  it('add mode PATCHes current + delta per coin (write contract)', async () => {
    getChar.mockResolvedValue(baseChar)
    updateSpy.mockResolvedValue(baseChar.currency)
    renderWithProviders(<Currency />)
    await screen.findByText('10.00')

    // Default mode is "add"; all coin inputs share the '+/-' placeholder, in COINS
    // order: [platinum, gold, electrum, silver, copper] → index 1 is gold.
    const goldInput = screen.getAllByPlaceholderText('+/-')[1]
    fireEvent.change(goldInput, { target: { value: '5' } })

    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    await waitFor(() =>
      expect(updateSpy).toHaveBeenCalledWith(5, {
        platinum: 0, gold: 15, electrum: 0, silver: 0, copper: 0,
      }),
    )
  })

  it('set mode keeps untouched coins at their current value', async () => {
    getChar.mockResolvedValue(baseChar)
    updateSpy.mockResolvedValue(baseChar.currency)
    renderWithProviders(<Currency />)
    await screen.findByText('10.00')

    await userEvent.click(screen.getByRole('button', { name: 'character.currency.mode_set' }))
    // In set mode placeholders become the current values; gold's is the unique '10'.
    fireEvent.change(screen.getByPlaceholderText('10'), { target: { value: '3' } })

    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    await waitFor(() =>
      expect(updateSpy).toHaveBeenCalledWith(5, {
        platinum: 0, gold: 3, electrum: 0, silver: 0, copper: 0,
      }),
    )
  })

  it('convert posts (source, target, amount) to the convert endpoint', async () => {
    getChar.mockResolvedValue(baseChar)
    convertSpy.mockResolvedValue(baseChar.currency)
    renderWithProviders(<Currency />)
    await screen.findByText('10.00')

    // Open the convert sheet (defaults gold → silver).
    await userEvent.click(screen.getByRole('button', { name: 'character.currency.convert' }))
    const sheet = await screen.findByTestId('sheet')

    fireEvent.change(within(sheet).getByPlaceholderText('0'), { target: { value: '2' } })
    await userEvent.click(within(sheet).getByRole('button', { name: 'character.currency.convert' }))

    await waitFor(() => expect(convertSpy).toHaveBeenCalledWith(5, 'gold', 'silver', 2))
  })
})

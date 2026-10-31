import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PendingSavesBanner from '@/components/PendingSavesBanner'

const { state, warning } = vi.hoisted(() => ({
  state: { saves: [] as unknown[], isMyTurn: false },
  warning: vi.fn(),
}))

vi.mock('@/hooks/usePendingSaves', () => ({ usePendingSaves: () => state }))
vi.mock('@/components/SaveRollSheet', () => ({ default: () => <div data-testid="sheet" /> }))
vi.mock('@/api/client', () => ({ api: { characters: { pendingSaves: { dismiss: vi.fn() } } } }))
vi.mock('@tanstack/react-query', () => ({ useQueryClient: () => ({ invalidateQueries: vi.fn() }) }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: { warning, light: vi.fn() } }))
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

const save = (over = {}) => ({ id: 1, slug: 'poisoned', ability: 'constitution', dc: 15, status: 'pending', created_at: '', ...over })

beforeEach(() => {
  state.saves = []
  state.isMyTurn = false
  warning.mockClear()
})

describe('PendingSavesBanner', () => {
  it('renders nothing without saves', () => {
    const { container } = render(<PendingSavesBanner charId={7} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('normal state is not strong and opens the sheet', async () => {
    state.saves = [save()]
    render(<PendingSavesBanner charId={7} />)
    expect(screen.getByTestId('pending-saves-banner')).toHaveAttribute('data-strong', 'false')
    expect(warning).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button'))
    expect(screen.getByTestId('sheet')).toBeInTheDocument()
  })

  it('is strong on my turn and warns once', () => {
    state.saves = [save()]
    state.isMyTurn = true
    const { rerender } = render(<PendingSavesBanner charId={7} />)
    expect(screen.getByTestId('pending-saves-banner')).toHaveAttribute('data-strong', 'true')
    rerender(<PendingSavesBanner charId={7} />)
    expect(warning).toHaveBeenCalledTimes(1)
  })

  it('keeps the sheet mounted after the saves list empties', async () => {
    state.saves = [save()]
    const { rerender } = render(<PendingSavesBanner charId={7} />)
    await userEvent.click(screen.getByRole('button'))
    state.saves = []
    rerender(<PendingSavesBanner charId={7} />)
    expect(screen.getByTestId('sheet')).toBeInTheDocument()
  })

  it('failed-only banner opens the sheet instead of dismissing', async () => {
    state.saves = [save({ status: 'failed' })]
    render(<PendingSavesBanner charId={7} />)
    await userEvent.click(screen.getByRole('button'))
    expect(screen.getByTestId('sheet')).toBeInTheDocument()
  })
})

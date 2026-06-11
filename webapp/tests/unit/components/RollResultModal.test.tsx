import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import RollResultModal, { type RollResult } from '@/components/RollResultModal'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/styles/motion', () => ({ spring: new Proxy({}, { get: () => ({}) }) }))
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
vi.mock('@/components/ui/ResultDialog', async () => {
  const React = await import('react')
  return {
    default: (p: { accent?: string; pulse?: boolean; title?: unknown; subtitle?: unknown; onClose?: () => void; extraActions?: unknown; children?: unknown }) =>
      React.createElement(
        'div',
        { 'data-testid': 'dialog', 'data-accent': p.accent, 'data-pulse': String(!!p.pulse) },
        p.subtitle ? React.createElement('div', { 'data-testid': 'rd-subtitle' }, p.subtitle) : null,
        p.extraActions ? React.createElement('div', { 'data-testid': 'rd-extra' }, p.extraActions) : null,
        React.createElement('button', { 'data-testid': 'rd-close', onClick: p.onClose }, 'close'),
        React.createElement('div', { 'data-testid': 'rd-body' }, p.children),
      ),
  }
})
vi.mock('@/components/InspirationRerollButton', async () => {
  const React = await import('react')
  return { default: (p: { onClick: () => void }) => React.createElement('button', { 'data-testid': 'inspiration', onClick: p.onClick }, 'reroll') }
})

// Contract: RollResult mirrors api/schemas/common.py::RollResult.
const result = (over: Partial<RollResult> = {}): RollResult => ({
  die: 15, bonus: 3, total: 18, is_critical: false, is_fumble: false, ...over,
})

describe('RollResultModal', () => {
  it('shows a neutral roll with the d20 (die) + bonus = total breakdown', () => {
    render(<RollResultModal result={result()} title="Tiro" onClose={() => {}} />)
    expect(screen.getByTestId('dialog')).toHaveAttribute('data-accent', 'default')
    expect(screen.getByText('15')).toBeInTheDocument()
    expect(screen.getByText(/d20 \(15\) \+3 =/)).toBeInTheDocument()
    expect(screen.getByText('18')).toBeInTheDocument()
  })

  it('a critical hit is gold, pulsing and shows the CRITICO banner', () => {
    render(<RollResultModal result={result({ is_critical: true })} title="T" onClose={() => {}} />)
    expect(screen.getByTestId('dialog')).toHaveAttribute('data-accent', 'gold')
    expect(screen.getByTestId('dialog')).toHaveAttribute('data-pulse', 'true')
    expect(screen.getByText('character.dice.critical_banner')).toBeInTheDocument()
  })

  it('a fumble is crimson and shows the FUMBLE banner', () => {
    render(<RollResultModal result={result({ is_fumble: true })} title="T" onClose={() => {}} />)
    expect(screen.getByTestId('dialog')).toHaveAttribute('data-accent', 'crimson')
    expect(screen.getByText('character.dice.fumble_banner')).toBeInTheDocument()
  })

  it('offers the inspiration reroll only when available and not already rerolled', async () => {
    const onInspirationReroll = vi.fn()
    const { rerender } = render(
      <RollResultModal result={result()} title="T" onClose={() => {}} inspirationAvailable onInspirationReroll={onInspirationReroll} />,
    )
    await userEvent.click(screen.getByTestId('inspiration'))
    expect(onInspirationReroll).toHaveBeenCalledTimes(1)
    rerender(
      <RollResultModal result={result()} title="T" onClose={() => {}} inspirationAvailable wasRerolled onInspirationReroll={onInspirationReroll} />,
    )
    expect(screen.queryByTestId('inspiration')).not.toBeInTheDocument()
    expect(screen.getByTestId('rd-subtitle')).toBeInTheDocument() // reroll badge
  })

  it('closes via the dialog', async () => {
    const onClose = vi.fn()
    render(<RollResultModal result={result()} title="T" onClose={onClose} />)
    await userEvent.click(screen.getByTestId('rd-close'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})

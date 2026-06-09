import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import HitDiceResultDialog from '@/pages/hp/HitDiceResultDialog'
import type { HitDiceSpendResult } from '@/api/client'

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
vi.mock('@/styles/motion', () => ({ spring: new Proxy({}, { get: () => ({}) }) }))
vi.mock('@/components/ui/ResultDialog', async () => {
  const React = await import('react')
  return {
    default: (p: { accent?: string; title?: unknown; onClose?: () => void; children?: unknown }) =>
      React.createElement(
        'div',
        { 'data-testid': 'result-dialog', 'data-accent': p.accent },
        React.createElement('div', { 'data-testid': 'rd-title' }, p.title),
        React.createElement('button', { 'data-testid': 'rd-close', onClick: p.onClose }, 'close'),
        React.createElement('div', { 'data-testid': 'rd-body' }, p.children),
      ),
  }
})

// Contract: matches api/routers/hp.py::HitDiceSpendResult field-for-field.
const result: HitDiceSpendResult = {
  rolls: [5, 4],
  con_bonus: 2,
  healed: 11,
  new_current_hp: 19,
}

describe('HitDiceResultDialog', () => {
  it('shows the healed amount, the individual rolls + CON bonus, and the new HP total', () => {
    render(<HitDiceResultDialog result={result} onClose={() => {}} />)
    expect(screen.getByTestId('result-dialog')).toHaveAttribute('data-accent', 'emerald')
    expect(screen.getByText('+11')).toBeInTheDocument()
    expect(screen.getByText(/\[5, 4\] \+2 \(COS\)/)).toBeInTheDocument()
    expect(screen.getByText('19')).toBeInTheDocument()
    expect(screen.getByText('character.hp.hit_dice_result')).toBeInTheDocument()
  })

  it('forwards onClose', async () => {
    const onClose = vi.fn()
    render(<HitDiceResultDialog result={result} onClose={onClose} />)
    await userEvent.click(screen.getByTestId('rd-close'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})

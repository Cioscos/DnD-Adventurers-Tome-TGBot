import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DeathSaveResultDialog from '@/pages/hp/DeathSaveResultDialog'
import type { DeathSaveRollResult } from '@/api/client'

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
    default: (p: { accent?: string; pulse?: boolean; title?: unknown; onClose?: () => void; children?: unknown }) =>
      React.createElement(
        'div',
        { 'data-testid': 'result-dialog', 'data-accent': p.accent, 'data-pulse': String(!!p.pulse) },
        React.createElement('div', { 'data-testid': 'rd-title' }, p.title),
        React.createElement('button', { 'data-testid': 'rd-close', onClick: p.onClose }, 'close'),
        React.createElement('div', { 'data-testid': 'rd-body' }, p.children),
      ),
  }
})

// Contract: this shape matches api/schemas/common.py::DeathSaveRollResult field-for-field.
const result = (over: Partial<DeathSaveRollResult> = {}): DeathSaveRollResult => ({
  die: 20,
  outcome: 'nat20',
  successes: 1,
  failures: 0,
  stable: false,
  revived: true,
  current_hp: 1,
  ...over,
})

describe('DeathSaveResultDialog', () => {
  it('nat20 → gold, pulsing, success verdict, revived message, big die value (D&D 5e revive rule)', () => {
    render(<DeathSaveResultDialog result={result()} onClose={() => {}} />)
    const dialog = screen.getByTestId('result-dialog')
    expect(dialog).toHaveAttribute('data-accent', 'gold')
    expect(dialog).toHaveAttribute('data-pulse', 'true')
    expect(screen.getByText('character.death_saves.nat20', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('character.death_saves.success')).toBeInTheDocument()
    expect(screen.getByText('character.death_saves.revived')).toBeInTheDocument()
    expect(screen.getByText('20')).toBeInTheDocument()
  })

  it('nat1 with 3 failures → crimson, pulsing, failure verdict, dead message', () => {
    render(
      <DeathSaveResultDialog
        result={result({ outcome: 'nat1', die: 1, successes: 0, failures: 3, revived: false })}
        onClose={() => {}}
      />,
    )
    const dialog = screen.getByTestId('result-dialog')
    expect(dialog).toHaveAttribute('data-accent', 'crimson')
    expect(dialog).toHaveAttribute('data-pulse', 'true')
    expect(screen.getByText('character.death_saves.nat1', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('character.death_saves.failure')).toBeInTheDocument()
    expect(screen.getByText('character.death_saves.dead_3_failures')).toBeInTheDocument()
  })

  it('plain success with 3 successes → emerald, not pulsing, stable message', () => {
    render(
      <DeathSaveResultDialog
        result={result({ outcome: 'success', die: 14, successes: 3, failures: 0, stable: true, revived: false })}
        onClose={() => {}}
      />,
    )
    const dialog = screen.getByTestId('result-dialog')
    expect(dialog).toHaveAttribute('data-accent', 'emerald')
    expect(dialog).toHaveAttribute('data-pulse', 'false')
    expect(screen.getByText('character.death_saves.success')).toBeInTheDocument()
    expect(screen.getByText('character.death_saves.stable_3_successes')).toBeInTheDocument()
  })

  it('plain failure → crimson, not pulsing, no nat20/nat1 banner', () => {
    render(
      <DeathSaveResultDialog
        result={result({ outcome: 'failure', die: 7, successes: 1, failures: 1, revived: false })}
        onClose={() => {}}
      />,
    )
    const dialog = screen.getByTestId('result-dialog')
    expect(dialog).toHaveAttribute('data-accent', 'crimson')
    expect(dialog).toHaveAttribute('data-pulse', 'false')
    expect(screen.getByText('character.death_saves.failure')).toBeInTheDocument()
    expect(screen.queryByText('character.death_saves.nat20', { exact: false })).not.toBeInTheDocument()
  })

  it('renders the success/failure tally and forwards onClose', async () => {
    const onClose = vi.fn()
    render(<DeathSaveResultDialog result={result({ successes: 2, failures: 1 })} onClose={onClose} />)
    expect(screen.getByText(/2\/3.*1\/3/)).toBeInTheDocument()
    await userEvent.click(screen.getByTestId('rd-close'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})

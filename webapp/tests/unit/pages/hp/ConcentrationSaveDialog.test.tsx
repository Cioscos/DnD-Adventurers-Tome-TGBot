import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ConcentrationSaveDialog from '@/pages/hp/ConcentrationSaveDialog'
import type { ConcentrationSaveResult } from '@/api/client'

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

// Contract: matches api/schemas/common.py::ConcentrationSaveResult (RollResult + dc/success/lost_concentration).
const result = (over: Partial<ConcentrationSaveResult> = {}): ConcentrationSaveResult => ({
  die: 12,
  bonus: 3,
  total: 15,
  description: '',
  dc: 10,
  success: true,
  lost_concentration: false,
  is_critical: false,
  is_fumble: false,
  ...over,
})

describe('ConcentrationSaveDialog', () => {
  it('passing save → emerald, not pulsing, success verdict; shows total and DC in the title', () => {
    render(<ConcentrationSaveDialog result={result()} onClose={() => {}} />)
    const dialog = screen.getByTestId('result-dialog')
    expect(dialog).toHaveAttribute('data-accent', 'emerald')
    expect(dialog).toHaveAttribute('data-pulse', 'false')
    expect(screen.getByText('character.spells.conc_save_success')).toBeInTheDocument()
    expect(screen.getByText('15')).toBeInTheDocument()
    expect(screen.getByText(/conc_save_title/)).toBeInTheDocument()
    expect(screen.getByText(/d20 \(12\) \+3/)).toBeInTheDocument()
  })

  it('critical → gold accent, pulsing, CRITICO banner', () => {
    render(<ConcentrationSaveDialog result={result({ is_critical: true })} onClose={() => {}} />)
    const dialog = screen.getByTestId('result-dialog')
    expect(dialog).toHaveAttribute('data-accent', 'gold')
    expect(dialog).toHaveAttribute('data-pulse', 'true')
    expect(screen.getByText(/critical_banner/)).toBeInTheDocument()
  })

  it('fumble that breaks concentration → crimson, pulsing, FUMBLE banner, fail verdict, lost-concentration note', () => {
    render(
      <ConcentrationSaveDialog
        result={result({ success: false, is_fumble: true, lost_concentration: true, total: 4 })}
        onClose={() => {}}
      />,
    )
    const dialog = screen.getByTestId('result-dialog')
    expect(dialog).toHaveAttribute('data-accent', 'crimson')
    expect(dialog).toHaveAttribute('data-pulse', 'true')
    expect(screen.getByText(/fumble_banner/)).toBeInTheDocument()
    expect(screen.getByText('character.spells.conc_save_fail')).toBeInTheDocument()
    expect(screen.getByText('character.spells.conc_lost')).toBeInTheDocument()
  })

  it('plain failure that keeps concentration → crimson, not pulsing, no lost-concentration note', () => {
    render(
      <ConcentrationSaveDialog
        result={result({ success: false, total: 8, lost_concentration: false })}
        onClose={() => {}}
      />,
    )
    expect(screen.getByTestId('result-dialog')).toHaveAttribute('data-pulse', 'false')
    expect(screen.getByText('character.spells.conc_save_fail')).toBeInTheDocument()
    expect(screen.queryByText('character.spells.conc_lost')).not.toBeInTheDocument()
  })

  it('renders a negative bonus without a leading + and forwards onClose', async () => {
    const onClose = vi.fn()
    render(<ConcentrationSaveDialog result={result({ bonus: -2, die: 6, total: 4 })} onClose={onClose} />)
    expect(screen.getByText(/d20 \(6\) -2/)).toBeInTheDocument()
    await userEvent.click(screen.getByTestId('rd-close'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})

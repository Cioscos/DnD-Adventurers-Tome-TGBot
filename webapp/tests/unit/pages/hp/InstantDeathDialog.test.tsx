import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import InstantDeathDialog from '@/pages/hp/InstantDeathDialog'

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

describe('InstantDeathDialog', () => {
  it('renders nothing when closed', () => {
    render(<InstantDeathDialog open={false} onClose={() => {}} />)
    expect(screen.queryByTestId('result-dialog')).not.toBeInTheDocument()
  })

  it('renders the crimson, pulsing massive-damage death dialog when open', () => {
    render(<InstantDeathDialog open onClose={() => {}} />)
    const dialog = screen.getByTestId('result-dialog')
    expect(dialog).toHaveAttribute('data-accent', 'crimson')
    expect(dialog).toHaveAttribute('data-pulse', 'true')
    expect(screen.getByText('character.death_saves.instant_death_title')).toBeInTheDocument()
    expect(screen.getByText('character.death_saves.instant_death_body')).toBeInTheDocument()
  })

  it('forwards onClose to the dialog', async () => {
    const onClose = vi.fn()
    render(<InstantDeathDialog open onClose={onClose} />)
    await userEvent.click(screen.getByTestId('rd-close'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})

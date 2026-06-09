import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ProgressionFullTableModal from '@/components/character/ProgressionFullTableModal'

const { progressionRowsSpy } = vi.hoisted(() => ({ progressionRowsSpy: vi.fn() }))

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
  return {
    m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }),
    AnimatePresence: (p: { children?: unknown }) => React.createElement(React.Fragment, null, p.children),
  }
})
vi.mock('@/lib/classProgression', () => ({
  progressionRows: progressionRowsSpy,
  localizeFeatures: (f: string) => f,
}))
vi.mock('@/store/overlayStore', () => ({ useRegisterOverlay: () => {} }))

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn()
})

const rows = [
  { proficiency_bonus: 2, features: 'Rage' },
  { proficiency_bonus: 2, features: 'Reckless Attack' },
  { proficiency_bonus: 2, features: 'Fast Movement' },
]

describe('ProgressionFullTableModal', () => {
  it('renders a row per progression level with its features', () => {
    progressionRowsSpy.mockReturnValue(rows)
    render(<ProgressionFullTableModal className="barbarian" currentLevel={2} onClose={() => {}} />)
    expect(screen.getByText('Rage')).toBeInTheDocument()
    expect(screen.getByText('Reckless Attack')).toBeInTheDocument()
    expect(screen.getByText('Fast Movement')).toBeInTheDocument()
  })

  it('highlights the current level row', () => {
    progressionRowsSpy.mockReturnValue(rows)
    render(<ProgressionFullTableModal className="barbarian" currentLevel={2} onClose={() => {}} />)
    expect(screen.getByText('Reckless Attack').closest('tr')).toHaveClass('bg-dnd-gold/15')
  })

  it('closes via the close button', async () => {
    progressionRowsSpy.mockReturnValue(rows)
    const onClose = vi.fn()
    render(<ProgressionFullTableModal className="barbarian" currentLevel={2} onClose={onClose} />)
    await userEvent.click(screen.getByRole('button', { name: 'common.close' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('closes when the backdrop is tapped', () => {
    progressionRowsSpy.mockReturnValue(rows)
    const onClose = vi.fn()
    render(<ProgressionFullTableModal className="barbarian" currentLevel={2} onClose={onClose} />)
    fireEvent.click(document.querySelector('.fixed.inset-0') as HTMLElement)
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})

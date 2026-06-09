import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ProgressionPreview from '@/components/character/ProgressionPreview'

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
  return { m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }) }
})
vi.mock('@/components/ui/Surface', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/lib/classProgression', () => ({
  progressionRows: progressionRowsSpy,
  localizeFeatures: (f: string) => f,
}))
vi.mock('@/components/character/ProgressionFullTableModal', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'full-table' }) }
})

const rows20 = Array.from({ length: 20 }, (_, i) => ({ proficiency_bonus: 2, features: `feat-${i + 1}` }))

describe('ProgressionPreview', () => {
  it('shows a no-data fallback when the class has no progression table', () => {
    progressionRowsSpy.mockReturnValue(null)
    render(<ProgressionPreview className="homebrewclass" currentLevel={1} />)
    expect(screen.getByText('character.equipment.progression.no_data')).toBeInTheDocument()
  })

  it('renders a 5-row window centred on the current level and marks it current', () => {
    progressionRowsSpy.mockReturnValue(rows20)
    render(<ProgressionPreview className="fighter" currentLevel={5} />)
    // computeWindow(5, 20) → L4..L8
    for (const lv of ['L4', 'L5', 'L6', 'L7', 'L8']) expect(screen.getByText(lv)).toBeInTheDocument()
    expect(screen.getByText('L5').closest('[aria-current]')).toHaveAttribute('aria-current', 'true')
  })

  it('shows the proficiency-bonus column for a single class but hides it for multiclass', () => {
    progressionRowsSpy.mockReturnValue(rows20)
    const { rerender } = render(<ProgressionPreview className="fighter" currentLevel={5} />)
    expect(screen.getAllByText('+2').length).toBe(5) // one PB per visible row
    rerender(<ProgressionPreview className="fighter" currentLevel={5} isMulticlass />)
    expect(screen.queryByText('+2')).not.toBeInTheDocument()
  })

  it('tapping a row opens the full progression table', async () => {
    progressionRowsSpy.mockReturnValue(rows20)
    render(<ProgressionPreview className="fighter" currentLevel={5} />)
    expect(screen.queryByTestId('full-table')).not.toBeInTheDocument()
    await userEvent.click(screen.getByText('L5'))
    expect(screen.getByTestId('full-table')).toBeInTheDocument()
  })
})

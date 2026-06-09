import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ClassTabs from '@/components/character/ClassTabs'

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

const classes = [
  { class_name: 'fighter', level: 5 },
  { class_name: 'wizard', level: 3 },
]

describe('ClassTabs', () => {
  it('renders nothing for a single-class character', () => {
    const { container } = render(<ClassTabs classes={[{ class_name: 'fighter', level: 5 }]} selected="fighter" onSelect={() => {}} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders one tab per class with its level for a multiclass character', () => {
    render(<ClassTabs classes={classes} selected="fighter" onSelect={() => {}} />)
    expect(screen.getAllByRole('tab')).toHaveLength(2)
    expect(screen.getByText('dnd.classes.fighter')).toBeInTheDocument()
    expect(screen.getByText('L5')).toBeInTheDocument()
  })

  it('marks the selected class as the active tab', () => {
    render(<ClassTabs classes={classes} selected="wizard" onSelect={() => {}} />)
    const tabs = screen.getAllByRole('tab')
    expect(tabs[0]).toHaveAttribute('aria-selected', 'false') // fighter
    expect(tabs[1]).toHaveAttribute('aria-selected', 'true') // wizard
  })

  it('selecting a tab fires onSelect with its class name', async () => {
    const onSelect = vi.fn()
    render(<ClassTabs classes={classes} selected="fighter" onSelect={onSelect} />)
    await userEvent.click(screen.getByRole('tab', { name: /dnd.classes.wizard/ }))
    expect(onSelect).toHaveBeenCalledWith('wizard')
  })
})

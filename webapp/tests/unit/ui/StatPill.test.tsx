import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import StatPill from '@/components/ui/StatPill'

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

describe('StatPill', () => {
  it('renders the label and value as a non-interactive span by default', () => {
    render(<StatPill label="AC" value={17} />)
    expect(screen.getByText('AC')).toBeInTheDocument()
    expect(screen.getByText('17')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('becomes a button and fires onClick when interactive', async () => {
    const onClick = vi.fn()
    render(<StatPill label="HP" value={10} onClick={onClick} />)
    await userEvent.click(screen.getByRole('button'))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('hides the value in icon-only mode until tapped (reveal-on-tap)', async () => {
    render(<StatPill iconOnly revealOnTap icon={<span>i</span>} value="42" aria-label="speed" />)
    expect(screen.queryByText('42')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'speed' }))
    expect(screen.getByText('42')).toBeInTheDocument()
  })
})

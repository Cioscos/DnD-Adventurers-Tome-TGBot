import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChipInput from '@/components/ui/ChipInput'

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

describe('ChipInput', () => {
  it('renders a chip per value', () => {
    render(<ChipInput values={['elfico', 'comune']} onChange={() => {}} />)
    expect(screen.getByText('elfico')).toBeInTheDocument()
    expect(screen.getByText('comune')).toBeInTheDocument()
  })

  it('removing a chip emits the filtered list', async () => {
    const onChange = vi.fn()
    render(<ChipInput values={['elfico', 'comune']} onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: 'Rimuovi elfico' }))
    expect(onChange).toHaveBeenCalledWith(['comune'])
  })

  it('Enter commits a new chip', async () => {
    const onChange = vi.fn()
    render(<ChipInput values={[]} onChange={onChange} placeholder="lingua" />)
    await userEvent.type(screen.getByPlaceholderText('lingua'), 'nanico{Enter}')
    expect(onChange).toHaveBeenCalledWith(['nanico'])
  })

  it('rejects a duplicate with an error and no change', async () => {
    const onChange = vi.fn()
    render(<ChipInput values={['comune']} onChange={onChange} />)
    await userEvent.type(screen.getByRole('textbox'), 'comune{Enter}')
    expect(screen.getByText(/già presente/)).toBeInTheDocument()
    expect(onChange).not.toHaveBeenCalled()
  })

  it('Backspace on an empty input removes the last chip', async () => {
    const onChange = vi.fn()
    render(<ChipInput values={['a', 'b']} onChange={onChange} />)
    const input = screen.getByRole('textbox')
    input.focus()
    await userEvent.keyboard('{Backspace}')
    expect(onChange).toHaveBeenCalledWith(['a'])
  })
})

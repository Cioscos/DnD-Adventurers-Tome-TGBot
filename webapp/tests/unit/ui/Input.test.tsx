import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import Input from '@/components/ui/Input'

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

describe('Input', () => {
  it('reports a change with the new value', () => {
    const onChange = vi.fn()
    render(<Input value="" onChange={onChange} placeholder="name" />)
    fireEvent.change(screen.getByPlaceholderText('name'), { target: { value: 'a' } })
    expect(onChange).toHaveBeenLastCalledWith('a')
  })

  it('commits the value on blur', () => {
    const onCommit = vi.fn()
    render(<Input value="5" onChange={() => {}} onCommit={onCommit} placeholder="n" />)
    fireEvent.blur(screen.getByPlaceholderText('n'))
    expect(onCommit).toHaveBeenCalledWith('5')
  })

  it('Enter blurs the field (which is what commits it) for non-textarea inputs', () => {
    render(<Input value="7" onChange={() => {}} onCommit={() => {}} placeholder="n" />)
    const el = screen.getByPlaceholderText('n')
    el.focus()
    expect(el).toHaveFocus()
    fireEvent.keyDown(el, { key: 'Enter' })
    expect(el).not.toHaveFocus()
  })

  it('shows a numeric range error and skips onCommit when out of range', () => {
    const onCommit = vi.fn()
    render(<Input type="number" value="25" max={20} onChange={() => {}} onCommit={onCommit} placeholder="n" />)
    fireEvent.blur(screen.getByPlaceholderText('n'))
    expect(screen.getByText('Massimo: 20')).toBeInTheDocument()
    expect(onCommit).not.toHaveBeenCalled()
  })

  it('renders an externally supplied error', () => {
    render(<Input value="x" onChange={() => {}} error="Campo obbligatorio" placeholder="n" />)
    expect(screen.getByText('Campo obbligatorio')).toBeInTheDocument()
  })
})

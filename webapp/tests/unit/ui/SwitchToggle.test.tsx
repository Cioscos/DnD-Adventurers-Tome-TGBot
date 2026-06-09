import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SwitchToggle from '@/components/ui/SwitchToggle'

vi.mock('@/styles/motion', () => ({ spring: new Proxy({}, { get: () => ({}) }) }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
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

describe('SwitchToggle', () => {
  it('exposes a switch role reflecting the checked state', () => {
    render(<SwitchToggle checked onChange={() => {}} aria-label="3D dice" />)
    expect(screen.getByRole('switch', { name: '3D dice' })).toHaveAttribute('aria-checked', 'true')
  })

  it('toggles to the opposite value on click', async () => {
    const onChange = vi.fn()
    render(<SwitchToggle checked={false} onChange={onChange} aria-label="t" />)
    await userEvent.click(screen.getByRole('switch'))
    expect(onChange).toHaveBeenCalledWith(true)
  })

  it('does not toggle when disabled', async () => {
    const onChange = vi.fn()
    render(<SwitchToggle checked={false} onChange={onChange} disabled aria-label="t" />)
    await userEvent.click(screen.getByRole('switch'))
    expect(onChange).not.toHaveBeenCalled()
  })

  it('renders label + hint and toggles when the row is tapped', async () => {
    const onChange = vi.fn()
    render(<SwitchToggle checked={false} onChange={onChange} label="Dadi 3D" hint="anteprima" />)
    expect(screen.getByText('Dadi 3D')).toBeInTheDocument()
    expect(screen.getByText('anteprima')).toBeInTheDocument()
    await userEvent.click(screen.getByText('Dadi 3D'))
    expect(onChange).toHaveBeenCalledWith(true)
  })
})

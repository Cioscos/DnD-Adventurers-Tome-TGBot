import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Surface from '@/components/ui/Surface'

vi.mock('@/styles/motion', () => ({ spring: new Proxy({}, { get: () => ({}) }) }))
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

describe('Surface', () => {
  it('renders its children', () => {
    render(<Surface>contenuto</Surface>)
    expect(screen.getByText('contenuto')).toBeInTheDocument()
  })

  it('applies the variant style class', () => {
    const { container } = render(<Surface variant="elevated">x</Surface>)
    expect(container.firstChild).toHaveClass('bg-dnd-surface-raised')
  })

  it('fires onClick when interactive', async () => {
    const onClick = vi.fn()
    render(<Surface onClick={onClick} role="button" aria-label="card">x</Surface>)
    await userEvent.click(screen.getByRole('button', { name: 'card' }))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('renders as a motion element when asMotion/layoutId is set', () => {
    const { container } = render(<Surface asMotion>x</Surface>)
    expect(container.firstChild).not.toBeNull()
    expect(screen.getByText('x')).toBeInTheDocument()
  })

  // Bug visto su telefono (Monete): un wrapper `display: contents` assorbiva space-y → spaziatura 0.
  it('space-y in className arriva ai figli: diretti senza ornamento, sul wrapper con ornamento', () => {
    const { container, rerender } = render(<Surface className="space-y-3"><p>a</p><p>b</p></Surface>)
    const surface = container.firstChild as HTMLElement
    expect(surface.children).toHaveLength(2)
    expect(surface).toHaveClass('space-y-3')
    rerender(<Surface ornamented className="space-y-3 p-6"><p>a</p><p>b</p></Surface>)
    const wrapper = screen.getByText('a').parentElement as HTMLElement
    expect(wrapper).toHaveClass('space-y-3')
    expect(wrapper).not.toHaveClass('p-6')
  })
})

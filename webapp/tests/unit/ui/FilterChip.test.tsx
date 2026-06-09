import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import FilterChip from '@/components/ui/FilterChip'

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

describe('FilterChip', () => {
  it('reflects the selected state via aria-pressed', () => {
    const { rerender } = render(<FilterChip label="Martial" selected={false} onToggle={() => {}} />)
    expect(screen.getByRole('button', { name: /Martial/ })).toHaveAttribute('aria-pressed', 'false')
    rerender(<FilterChip label="Martial" selected onToggle={() => {}} />)
    expect(screen.getByRole('button', { name: /Martial/ })).toHaveAttribute('aria-pressed', 'true')
  })

  it('fires onToggle when tapped', async () => {
    const onToggle = vi.fn()
    render(<FilterChip label="Fire" selected={false} onToggle={onToggle} />)
    await userEvent.click(screen.getByRole('button', { name: /Fire/ }))
    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  it('renders an optional count badge', () => {
    render(<FilterChip label="Tag" selected count={3} onToggle={() => {}} />)
    expect(screen.getByText('3')).toBeInTheDocument()
  })
})

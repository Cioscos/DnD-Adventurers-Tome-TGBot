import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import ProgressTriad from '@/components/ui/ProgressTriad'

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

const barStyle = (c: HTMLElement) => (c.querySelector('.origin-left') as HTMLElement).getAttribute('style') ?? ''

describe('ProgressTriad', () => {
  it('shows the default "value / max" numeric tag when labelled', () => {
    render(<ProgressTriad value={12} max={150} label="Carico" />)
    expect(screen.getByText('12 / 150')).toBeInTheDocument()
  })

  it('uses an explicit display string when provided', () => {
    render(<ProgressTriad value={12} max={150} label="Carico" display="12.4 / 150 lb" />)
    expect(screen.getByText('12.4 / 150 lb')).toBeInTheDocument()
  })

  it('colors the bar emerald below the amber threshold', () => {
    const { container } = render(<ProgressTriad value={50} max={100} />)
    expect(barStyle(container)).toContain('emerald')
  })

  it('colors the bar amber past the amber threshold', () => {
    const { container } = render(<ProgressTriad value={80} max={100} />)
    expect(barStyle(container)).toContain('amber')
  })

  it('colors the bar crimson when overloaded', () => {
    const { container } = render(<ProgressTriad value={110} max={100} />)
    expect(barStyle(container)).toContain('crimson')
  })
})

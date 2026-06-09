import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import Reveal from '@/components/ui/Reveal'

vi.mock('@/styles/motion', () => ({
  motionVariants: { fadeUp: {} },
  spring: new Proxy({}, { get: () => ({}) }),
  stagger: { list: 0.05 },
}))
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

describe('Reveal', () => {
  it('Stagger renders its children', () => {
    render(
      <Reveal.Stagger>
        <Reveal.Item>uno</Reveal.Item>
        <Reveal.Item>due</Reveal.Item>
      </Reveal.Stagger>,
    )
    expect(screen.getByText('uno')).toBeInTheDocument()
    expect(screen.getByText('due')).toBeInTheDocument()
  })

  it('Item renders its content', () => {
    render(<Reveal.Item>contenuto</Reveal.Item>)
    expect(screen.getByText('contenuto')).toBeInTheDocument()
  })
})

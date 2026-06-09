import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/react'
import HPGauge from '@/components/ui/HPGauge'

// Mock framer-motion: `m.*` lazy components need a LazyMotion ancestor to render
// in a real app, and `useReducedMotion` reads window.matchMedia (absent in jsdom).
// We render plain DOM elements and strip motion-only props so React doesn't warn
// about unknown attributes — leaving the structural markup (segments, pulse class)
// fully assertable.
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION_PROPS = new Set([
    'initial', 'animate', 'exit', 'transition', 'variants',
    'whileHover', 'whileTap', 'whileInView', 'whileFocus', 'whileDrag',
    'drag', 'dragConstraints', 'layout', 'layoutId',
  ])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION_PROPS.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return {
    useReducedMotion: () => false,
    m: new Proxy(
      {},
      { get: (_t: object, tag: string | symbol) => make(String(tag)) },
    ),
  }
})

describe('HPGauge', () => {
  it('renders exactly 10 segment cells in segmented mode (default)', () => {
    const { container } = render(<HPGauge current={20} max={20} />)
    expect(container.querySelectorAll('.flex-1').length).toBe(10)
  })

  it('adds the danger pulse class at low HP (<= 25%)', () => {
    const { container } = render(<HPGauge current={2} max={20} />) // 10%
    expect((container.firstChild as HTMLElement).className).toContain('animate-pulse-danger')
  })

  it('does NOT pulse at healthy HP (> 25%)', () => {
    const { container } = render(<HPGauge current={20} max={20} />) // 100%
    expect((container.firstChild as HTMLElement).className).not.toContain('animate-pulse-danger')
  })

  it('renders without crashing when max is 0 (avoids divide-by-zero)', () => {
    const { container } = render(<HPGauge current={0} max={0} />)
    expect(container.querySelectorAll('.flex-1').length).toBe(10)
  })

  it('renders a single bar (no segment cells) when segmented is false', () => {
    const { container } = render(<HPGauge current={10} max={20} segmented={false} />)
    expect(container.querySelectorAll('.flex-1').length).toBe(0)
  })

  it('renders temp-HP overlay segments without crashing when temp > 0', () => {
    const { container } = render(<HPGauge current={10} max={20} temp={5} />)
    expect(container.querySelectorAll('.flex-1').length).toBe(10)
  })
})

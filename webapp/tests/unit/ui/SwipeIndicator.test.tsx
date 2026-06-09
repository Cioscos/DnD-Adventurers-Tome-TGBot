import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/react'
import SwipeIndicator from '@/components/ui/SwipeIndicator'

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

describe('SwipeIndicator', () => {
  it('renders nothing when there is no direction', () => {
    const { container } = render(<SwipeIndicator direction={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders a left-edge chevron when swiping left', () => {
    const { container } = render(<SwipeIndicator direction="left" progress={0.5} />)
    expect(container.querySelector('.left-2')).not.toBeNull()
    expect(container.querySelector('.right-2')).toBeNull()
  })

  it('renders a right-edge chevron when swiping right', () => {
    const { container } = render(<SwipeIndicator direction="right" progress={0.5} />)
    expect(container.querySelector('.right-2')).not.toBeNull()
    expect(container.querySelector('.left-2')).toBeNull()
  })
})

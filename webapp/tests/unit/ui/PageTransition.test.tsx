import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../utils/renderWithProviders'
import PageTransition from '@/components/ui/PageTransition'

vi.mock('@/styles/motion', () => ({ pageTransition: {} }))
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'drag', 'layout', 'mode'])
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

describe('PageTransition', () => {
  it('renders the wrapped route content', () => {
    renderWithProviders(<PageTransition><div>pagina</div></PageTransition>)
    expect(screen.getByText('pagina')).toBeInTheDocument()
  })
})

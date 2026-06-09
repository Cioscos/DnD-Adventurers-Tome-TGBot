import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import AnimatedNumber from '@/components/ui/AnimatedNumber'

// Reduce framer to a synchronous passthrough so the formatting transform renders
// its final string immediately (no spring animation in jsdom).
vi.mock('framer-motion', async () => {
  const React = await import('react')
  return {
    m: { span: (p: { className?: string; children?: unknown }) => React.createElement('span', { className: p.className }, p.children) },
    useReducedMotion: () => true,
    useSpring: (v: number) => ({ _v: v, jump() {}, set() {} }),
    useTransform: (src: { _v: number }, fn: (n: number) => string) => fn(src._v),
  }
})

// Mirror the component's exact formatting so the test is robust to ICU/locale data.
const fmt = (v: number, p = 0) => v.toLocaleString('it-IT', { minimumFractionDigits: p, maximumFractionDigits: p })

describe('AnimatedNumber', () => {
  it('formats an integer with it-IT grouping', () => {
    render(<AnimatedNumber value={1234} />)
    expect(screen.getByText(fmt(1234))).toBeInTheDocument()
  })

  it('applies prefix and suffix around the formatted value', () => {
    render(<AnimatedNumber value={1234} prefix="+" suffix=" XP" />)
    expect(screen.getByText(`+${fmt(1234)} XP`)).toBeInTheDocument()
  })

  it('honors the requested precision', () => {
    render(<AnimatedNumber value={12.5} precision={1} />)
    expect(screen.getByText(fmt(12.5, 1))).toBeInTheDocument()
  })
})

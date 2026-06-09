import { describe, it, expect, beforeEach, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import ScrollArea from '@/components/ScrollArea'

beforeAll(() => {
  // jsdom has no IntersectionObserver — stub one that never fires (stays "not at bottom").
  class IO {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  ;(globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = IO
})
beforeEach(() => localStorage.clear())

describe('ScrollArea', () => {
  it('renders its children', () => {
    render(<ScrollArea><p>contenuto lungo</p></ScrollArea>)
    expect(screen.getByText('contenuto lungo')).toBeInTheDocument()
  })

  it('shows the scroll hint on first visit (hint not yet seen)', () => {
    render(<ScrollArea><p>x</p></ScrollArea>)
    expect(screen.getByText(/scorri/)).toBeInTheDocument()
  })

  it('hides the scroll hint once it has been seen', () => {
    localStorage.setItem('scroll-hint-seen', '1')
    render(<ScrollArea><p>x</p></ScrollArea>)
    expect(screen.queryByText(/scorri/)).not.toBeInTheDocument()
  })
})

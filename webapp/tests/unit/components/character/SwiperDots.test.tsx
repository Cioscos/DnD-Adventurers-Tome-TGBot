import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SwiperDots from '@/components/character/SwiperDots'

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

const labels: [string, string, string] = ['Hero', 'Equipment', 'Menu']

describe('SwiperDots', () => {
  it('renders three tabs with their labels', () => {
    render(<SwiperDots active={0} onSelect={() => {}} labels={labels} />)
    const tabs = screen.getAllByRole('tab')
    expect(tabs).toHaveLength(3)
    expect(screen.getByRole('tab', { name: 'Equipment' })).toBeInTheDocument()
  })

  it('marks the active screen as selected', () => {
    render(<SwiperDots active={1} onSelect={() => {}} labels={labels} />)
    const tabs = screen.getAllByRole('tab')
    expect(tabs[0]).toHaveAttribute('aria-selected', 'false')
    expect(tabs[1]).toHaveAttribute('aria-selected', 'true')
    expect(tabs[2]).toHaveAttribute('aria-selected', 'false')
  })

  it('selects a screen index when a dot is tapped', async () => {
    const onSelect = vi.fn()
    render(<SwiperDots active={0} onSelect={onSelect} labels={labels} />)
    await userEvent.click(screen.getByRole('tab', { name: 'Menu' }))
    expect(onSelect).toHaveBeenCalledWith(2)
  })
})

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import HeroXPBar from '@/components/ui/HeroXPBar'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
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
// xpThresholds is the real lib (D&D 5e XP table: level 2 = 300 XP).

describe('HeroXPBar', () => {
  it('shows the level-up prompt when the XP-derived level exceeds the class level', () => {
    render(<HeroXPBar currentXP={300} totalClassLevel={1} />)
    expect(screen.getByText('character.xp.bar.level_up')).toBeInTheDocument()
  })

  it('renders a progress bar with the current XP as aria-valuenow when not maxed', () => {
    render(<HeroXPBar currentXP={100} totalClassLevel={5} />)
    const bar = screen.getByRole('progressbar')
    expect(bar).toHaveAttribute('aria-valuenow', '100')
  })

  it('suppresses the level-up prompt for a character with no classes', () => {
    render(<HeroXPBar currentXP={300} totalClassLevel={0} />)
    expect(screen.queryByText('character.xp.bar.level_up')).not.toBeInTheDocument()
  })
})

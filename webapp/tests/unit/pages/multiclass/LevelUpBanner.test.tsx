import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import LevelUpBanner from '@/pages/multiclass/LevelUpBanner'

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
vi.mock('@/styles/motion', () => ({ spring: new Proxy({}, { get: () => ({}) }) }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))

describe('LevelUpBanner', () => {
  it('renders the default level-up label', () => {
    render(<LevelUpBanner onOpen={() => {}} />)
    expect(screen.getByRole('button', { name: 'character.xp.level_up_available' })).toBeInTheDocument()
  })

  it('uses a custom label key when provided', () => {
    render(<LevelUpBanner onOpen={() => {}} labelKey="character.multiclass.level_up_here" />)
    expect(screen.getByRole('button', { name: 'character.multiclass.level_up_here' })).toBeInTheDocument()
  })

  it('fires onOpen when tapped', async () => {
    const onOpen = vi.fn()
    render(<LevelUpBanner onOpen={onOpen} />)
    await userEvent.click(screen.getByRole('button'))
    expect(onOpen).toHaveBeenCalledTimes(1)
  })
})

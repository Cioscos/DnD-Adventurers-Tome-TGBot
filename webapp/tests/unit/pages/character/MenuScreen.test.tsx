import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MenuScreen from '@/pages/character/MenuScreen'

const { navigateSpy } = vi.hoisted(() => ({ navigateSpy: vi.fn() }))
vi.mock('react-router-dom', () => ({ useNavigate: () => navigateSpy }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/styles/motion', () => ({ spring: new Proxy({}, { get: () => ({}) }), stagger: { listTight: 0.03 } }))
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
vi.mock('@/components/ui/SectionDivider', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/Reveal', async () => {
  const React = await import('react')
  return { default: { Stagger: (p: { children?: unknown }) => React.createElement('div', null, p.children), Item: (p: { children?: unknown }) => React.createElement('div', null, p.children) } }
})

describe('MenuScreen', () => {
  it('renders the menu sections and item labels', () => {
    render(<MenuScreen charId={7} />)
    expect(screen.getByText('character.menu.sections.combat')).toBeInTheDocument()
    expect(screen.getByText('character.menu.hp')).toBeInTheDocument()
    expect(screen.getByText('character.menu.homebrew')).toBeInTheDocument()
  })

  it('navigates to the character sub-page on item tap', async () => {
    render(<MenuScreen charId={7} />)
    await userEvent.click(screen.getByText('character.menu.hp'))
    expect(navigateSpy).toHaveBeenCalledWith('/char/7/hp')
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AutoModeBanner from '@/components/character/AutoModeBanner'

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
  return {
    m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }),
    AnimatePresence: (p: { children?: unknown }) => React.createElement(React.Fragment, null, p.children),
  }
})
vi.mock('@/styles/motion', () => ({ ease: {}, spring: new Proxy({}, { get: () => ({}) }) }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/components/ui/Surface', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})

beforeEach(() => localStorage.clear())

describe('AutoModeBanner', () => {
  it('is expanded on first access (no stored preference) and shows the hint + settings shortcut', () => {
    render(<AutoModeBanner onGoToSettings={() => {}} />)
    expect(screen.getByText('character.slots.auto_hint')).toBeInTheDocument()
    expect(screen.getByText('character.slots.go_to_settings')).toBeInTheDocument()
  })

  it('collapses when toggled and persists the closed state', async () => {
    render(<AutoModeBanner onGoToSettings={() => {}} />)
    const pill = screen.getByRole('button', { expanded: true })
    await userEvent.click(pill)
    expect(screen.getByRole('button', { expanded: false })).toBeInTheDocument()
    expect(screen.queryByText('character.slots.auto_hint')).not.toBeInTheDocument()
    expect(localStorage.getItem('dnd:slots-auto-banner')).toBe('closed')
  })

  it('starts collapsed when the stored preference is "closed"', () => {
    localStorage.setItem('dnd:slots-auto-banner', 'closed')
    render(<AutoModeBanner onGoToSettings={() => {}} />)
    expect(screen.queryByText('character.slots.auto_hint')).not.toBeInTheDocument()
  })

  it('invokes onGoToSettings from the shortcut', async () => {
    const onGoToSettings = vi.fn()
    render(<AutoModeBanner onGoToSettings={onGoToSettings} />)
    await userEvent.click(screen.getByText('character.slots.go_to_settings'))
    expect(onGoToSettings).toHaveBeenCalledTimes(1)
  })
})

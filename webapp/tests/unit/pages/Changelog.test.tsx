import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import Changelog from '@/pages/Changelog'
import { changelog } from '@/lib/version'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/hooks/useReducedMotion', () => ({ useReducedMotion: () => true }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'drag', 'layout'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return { m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }), AnimatePresence: (p: { children?: unknown }) => React.createElement(React.Fragment, null, p.children) }
})
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { title?: unknown; children?: unknown }) => React.createElement('div', null, React.createElement('h1', null, p.title), p.children) }
})
vi.mock('@/components/ui/Surface', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/EmptyState', async () => {
  const React = await import('react')
  return { default: (p: { title?: unknown }) => React.createElement('div', null, p.title) }
})

describe('Changelog', () => {
  it('lists each release with its version, newest marked current', () => {
    render(<Changelog />)
    expect(screen.getByText(`v${changelog[0].version}`)).toBeInTheDocument()
    expect(screen.getByText('changelog.current')).toBeInTheDocument()
    expect(screen.getAllByText(changelog[0].date).length).toBeGreaterThan(0)
  })

  it('expands the newest entry by default showing its category sections', () => {
    render(<Changelog />)
    // entries[0] has at least one of added/improved/fixed; their section headers render when open.
    const headers = ['changelog.sections.added', 'changelog.sections.improved', 'changelog.sections.fixed']
    expect(headers.some((h) => screen.queryByText(h))).toBe(true)
  })
})

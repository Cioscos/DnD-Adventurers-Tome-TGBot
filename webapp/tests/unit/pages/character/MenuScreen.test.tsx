import { describe, it, expect, vi } from 'vitest'
import { render as rtlRender, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactElement } from 'react'
import MenuScreen from '@/pages/character/MenuScreen'
import type { CharacterFull } from '@/types'

const { navigateSpy, restSpy } = vi.hoisted(() => ({ navigateSpy: vi.fn(), restSpy: vi.fn() }))
vi.mock('@/dice/useAnimatedRoll', () => ({ useAnimatedRoll: () => async () => undefined }))
vi.mock('@/api/client', () => ({
  api: { characters: { rest: restSpy, spendHitDice: vi.fn() } },
  ApiError: class extends Error {},
}))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }) }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
vi.mock('@/components/ui/ConfirmSheet', async () => {
  const React = await import('react')
  return {
    default: (p: { open: boolean; onConfirm: () => void; confirmLabel: string }) =>
      p.open ? React.createElement('button', { onClick: p.onConfirm }, `confirm:${p.confirmLabel}`) : null,
  }
})
vi.mock('@/pages/hp/HitDiceModal', async () => {
  const React = await import('react')
  return { default: (p: { onConfirmRest: () => void }) => React.createElement('button', { onClick: p.onConfirmRest }, 'short-modal-confirm') }
})
vi.mock('@/pages/hp/HitDiceResultDialog', () => ({ default: () => null }))

const makeChar = (over: Partial<CharacterFull> = {}) =>
  ({ id: 7, is_dead: false, classes: [], ...over }) as unknown as CharacterFull
const render = (ui: ReactElement) =>
  rtlRender(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>)
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
    render(<MenuScreen char={makeChar()} />)
    expect(screen.getByText('character.menu.sections.combat')).toBeInTheDocument()
    expect(screen.getByText('character.menu.hp')).toBeInTheDocument()
    expect(screen.getByText('character.menu.homebrew')).toBeInTheDocument()
  })

  it('navigates to the character sub-page on item tap', async () => {
    render(<MenuScreen char={makeChar()} />)
    await userEvent.click(screen.getByText('character.menu.hp'))
    expect(navigateSpy).toHaveBeenCalledWith('/char/7/hp')
  })

  it('conditions tile is in the combat section', () => {
    render(<MenuScreen char={makeChar()} />)
    const combat = screen.getByText('character.menu.sections.combat')
    const magic = screen.getByText('character.menu.sections.magic')
    const cond = screen.getByText('character.menu.conditions')
    expect(combat.compareDocumentPosition(cond) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(cond.compareDocumentPosition(magic) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('rest tile opens the sheet with short and long', async () => {
    navigateSpy.mockClear()
    render(<MenuScreen char={makeChar()} />)
    await userEvent.click(screen.getByText('character.menu.rest'))
    expect(screen.getByText('character.quick_actions.rest_short')).toBeInTheDocument()
    expect(screen.getByText('character.quick_actions.rest_long')).toBeInTheDocument()
    expect(navigateSpy).not.toHaveBeenCalled()
  })

  it('rest tile is hidden for dead characters', () => {
    render(<MenuScreen char={makeChar({ is_dead: true })} />)
    expect(screen.queryByText('character.menu.rest')).not.toBeInTheDocument()
  })

  it('long rest asks confirmation then calls api', async () => {
    restSpy.mockResolvedValue(makeChar())
    render(<MenuScreen char={makeChar()} />)
    await userEvent.click(screen.getByText('character.menu.rest'))
    await userEvent.click(screen.getByText('character.quick_actions.rest_long'))
    expect(restSpy).not.toHaveBeenCalled()
    await userEvent.click(screen.getByText('confirm:character.quick_actions.rest_long'))
    expect(restSpy).toHaveBeenCalledWith(7, 'long')
  })
})

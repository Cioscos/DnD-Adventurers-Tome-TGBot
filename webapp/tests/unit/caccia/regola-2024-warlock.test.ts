import { createElement } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderWithProviders } from '../utils/renderWithProviders'
import LevelUpModal from '@/pages/multiclass/LevelUpModal'
import RestSheet from '@/components/character/RestSheet'
import type { CharacterFull } from '@/types'

const mocks = vi.hoisted(() => ({
  distribute: vi.fn(), spendHitDice: vi.fn(), rest: vi.fn(), restPreview: vi.fn(), featureUse: vi.fn(), endActiveState: vi.fn(),
}))

vi.mock('@/api/client', async (orig) => ({
  ...(await orig<Record<string, unknown>>()),
  api: {
    classes: { distribute: mocks.distribute },
    characters: { spendHitDice: mocks.spendHitDice, rest: mocks.rest, restPreview: mocks.restPreview,
      featureUse: mocks.featureUse, endActiveState: mocks.endActiveState },
  },
}))
vi.mock('react-i18next', async (orig) => ({
  ...(await orig<typeof import('react-i18next')>()), useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }),
}))
vi.mock('framer-motion', async (orig) => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'layout', 'onAnimationComplete'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return { ...(await orig<Record<string, unknown>>()), m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }) }
})
vi.mock('sonner', () => ({ toast: { success: vi.fn(), info: vi.fn(), error: vi.fn() } }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: vi.fn(), success: vi.fn(), info: vi.fn() }) }))
vi.mock('@/dice/useAnimatedRoll', () => ({ useAnimatedRoll: () => async () => undefined }))
vi.mock('@/store/overlayStore', async (orig) => ({ ...(await orig<Record<string, unknown>>()), useRegisterOverlay: () => {} }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
vi.mock('@/components/ui/ConfirmSheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; body?: unknown; onConfirm?: () => void }) => (p.open
    ? React.createElement('div', null, p.body, React.createElement('button', { onClick: p.onConfirm }, 'confirm')) : null) }
})
vi.mock('@/pages/hp/HitDiceModal', async () => {
  const React = await import('react')
  return {
    default: (p: { onConfirmRest: () => void; preview?: unknown }) =>
      React.createElement('div', { 'data-testid': 'hit-dice-modal' }, React.createElement('button', { onClick: p.onConfirmRest }, 'rest'), p.preview),
  }
})
vi.mock('@/pages/hp/HitDiceResultDialog', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'hit-die-result' }) }
})

afterEach(() => { vi.clearAllMocks() })

const tomo2024 = {
  id: 7, rules_edition: '2024', settings: {}, ability_scores: [], active_states: [],
  classes: [{ id: 1, class_name: 'warlock', level: 3, hit_die: 8 }],
  abilities: [{ id: 5, feature_key: 'warlock.pact_of_the_tome', name: 'Patto del Tomo' }],
} as unknown as CharacterFull

const warlock2024 = {
  id: 9, rules_edition: '2024', settings: {}, ability_scores: [],
  classes: [{ id: 1, class_name: 'warlock', level: 1, hit_die: 8 }],
} as unknown as CharacterFull

describe('caccia: regola 2024 warlock', () => {
  // caccia: {"id": "CB-2675", "fonte": "2024 · Warlock · Patto del Tomo · pag. 157", "zona": "regola:2024/warlock", "voce": "regola", "copre": ["carta:2024/classes/warlock.md#Patto del Tomo / Pact of the Tome (Suppliche Occulte, pag. 157)", "route:/char/:id", "route:/char/:id/hp"]}
  it.fails('il riposo breve offre di rifare le scelte del Libro delle Ombre', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    render(createElement(QueryClientProvider, { client: qc }, createElement(RestSheet, { char: tomo2024, open: true, onClose: vi.fn() })))
    await userEvent.click(screen.getByText('character.quick_actions.rest_short'))
    expect(screen.getByTestId('hit-dice-modal')).toBeTruthy()
    expect(screen.queryByTestId('tome-reopen')).not.toBeNull()
  })

  // caccia: {"id": "CB-2676", "fonte": "2024 · Warlock · Tabella di classe, Suppliche Occulte e Sottoclasse · pag. 153-154", "zona": "regola:2024/warlock", "voce": "edizioni", "copre": ["carta:2024/classes/warlock.md#Sottoclasse del Warlock / Warlock Subclass (Warlock 3, pag. 154)", "carta:2024/classes/warlock.md#Suppliche Occulte / Eldritch Invocations (Warlock 1, pag. 153)", "route:/char/:id/xp"]}
  it.fails('la salita di livello di un warlock 2024 non annuncia il Dono del Patto del 2014', () => {
    renderWithProviders(createElement(LevelUpModal, { char: warlock2024, xpLevel: 2, onClose: vi.fn() }))
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.queryByText(/Pact Boon/)).toBeNull()
  })
})

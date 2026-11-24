import { createElement } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../utils/renderWithProviders'
import LevelUpModal from '@/pages/multiclass/LevelUpModal'
import type { CharacterFull } from '@/types'

vi.mock('@/api/client', () => ({ api: { classes: { distribute: vi.fn() } } }))
vi.mock('react-i18next', async (orig) => ({
  ...(await orig<typeof import('react-i18next')>()), useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }),
}))
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'layout', 'onAnimationComplete'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return { m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }) }
})
vi.mock('sonner', () => ({ toast: { success: vi.fn(), info: vi.fn() } }))
vi.mock('@/store/overlayStore', () => ({ useRegisterOverlay: () => {} }))
vi.mock('@/auth/telegram', () => ({ haptic: { success: () => {}, error: () => {}, medium: () => {} } }))

const bardo2024 = {
  id: 9, rules_edition: '2024', settings: {}, ability_scores: [],
  classes: [{ id: 1, class_name: 'bard', level: 1, hit_die: 8 }],
} as unknown as CharacterFull

describe('caccia: regola 2024 bardo', () => {
  // caccia: {"id": "CB-2215", "fonte": "2024 · Bardo · Tabella di classe, Maestria e Factotum · pag. 59-61", "zona": "regola:2024/bard", "voce": "edizioni", "copre": ["carta:2024/classes/bard.md#Maestria / Expertise (Bardo 2, pag. 60)", "carta:2024/classes/bard.md#Factotum / Jack of All Trades (Bardo 2, pag. 60)", "route:/char/:id/xp"]}
  it.fails("la salita di livello di un bardo 2024 non annuncia il Canto di Riposo del 2014", () => {
    renderWithProviders(createElement(LevelUpModal, { char: bardo2024, xpLevel: 2, onClose: vi.fn() }))
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.queryByText(/Song of Rest/)).toBeNull()
  })
})

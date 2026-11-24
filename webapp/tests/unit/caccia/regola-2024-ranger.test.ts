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

const ranger2024 = {
  id: 9, rules_edition: '2024', settings: {}, ability_scores: [],
  classes: [{ id: 1, class_name: 'ranger', level: 2, hit_die: 10 }],
} as unknown as CharacterFull

describe('caccia: regola 2024 ranger', () => {
  // caccia: {"id": "CB-2520", "fonte": "2024 · Ranger · Tabella di classe e Sottoclasse del Ranger · pag. 119-120", "zona": "regola:2024/ranger", "voce": "edizioni", "copre": ["carta:2024/classes/ranger.md#Sottoclasse del Ranger / Ranger Subclass (Ranger 3, pag. 120)", "route:/char/:id/xp"]}
  it('la salita di livello di un ranger 2024 non annuncia la Consapevolezza Primordiale del 2014', () => {
    renderWithProviders(createElement(LevelUpModal, { char: ranger2024, xpLevel: 3, onClose: vi.fn() }))
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.queryByText(/Primeval Awareness/)).toBeNull()
  })
})

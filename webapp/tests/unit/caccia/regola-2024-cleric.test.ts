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

const chierico2024 = {
  id: 9, rules_edition: '2024', settings: {}, ability_scores: [],
  classes: [{ id: 1, class_name: 'cleric', level: 4, hit_die: 8 }],
} as unknown as CharacterFull

describe('caccia: regola 2024 chierico', () => {
  // caccia: {"id": "CB-2267", "fonte": "2024 · Chierico · Tabella di classe e Bruciare Non Morti · pag. 69-71", "zona": "regola:2024/cleric", "voce": "edizioni", "copre": ["carta:2024/classes/cleric.md#Bruciare Non Morti / Sear Undead (Chierico 5, pag. 71)", "carta:2024/classes/cleric.md#Incanalare Divinità / Channel Divinity (Chierico 2, pag. 70)", "route:/char/:id/xp"]}
  it.fails('la salita di livello di un chierico 2024 non annuncia Distruggere Non Morti del 2014', () => {
    renderWithProviders(createElement(LevelUpModal, { char: chierico2024, xpLevel: 5, onClose: vi.fn() }))
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.queryByText(/Destroy Undead/)).toBeNull()
  })
})

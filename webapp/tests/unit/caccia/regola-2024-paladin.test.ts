import { createElement } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../utils/renderWithProviders'
import LevelUpModal from '@/pages/multiclass/LevelUpModal'
import type { CharacterFull } from '@/types'

vi.mock('@/api/client', () => ({ api: { classes: { distribute: vi.fn() } } }))
vi.mock('react-i18next', async (orig) => ({
  ...(await orig<typeof import('react-i18next')>()),
  useTranslation: () => ({ t: (k: string, o?: { level?: number }) => (o?.level ? `${k}:${o.level}` : k), i18n: { language: 'it' } }),
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

const paladino2024 = {
  id: 9, rules_edition: '2024', settings: {}, ability_scores: [],
  classes: [{ id: 1, class_name: 'paladin', level: 1, hit_die: 10 }],
} as unknown as CharacterFull

describe('caccia: regola 2024 paladino', () => {
  // caccia: {"id": "CB-2463", "fonte": "2024 · Paladino · Tabella di classe, slot di 1° livello già al 1° · pag. 109", "zona": "regola:2024/paladin", "voce": "edizioni", "copre": ["carta:2024/classes/paladin.md#Incantesimi / Spellcasting (Paladino 1, pag. 109)", "route:/char/:id/xp"]}
  it('la salita al 2° livello di un paladino 2024 non annuncia nuovi slot di 1° livello, che ha già dal 1°', () => {
    renderWithProviders(createElement(LevelUpModal, { char: paladino2024, xpLevel: 2, onClose: vi.fn() }))
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.queryByText('character.multiclass.level_up.new_spell_slot:1')).toBeNull()
  })
})

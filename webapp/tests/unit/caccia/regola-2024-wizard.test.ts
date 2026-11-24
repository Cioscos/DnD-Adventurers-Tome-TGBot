import { createElement } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../utils/renderWithProviders'
import LevelUpModal from '@/pages/multiclass/LevelUpModal'
import MemorizeSpellPicker from '@/components/character/MemorizeSpellPicker'
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

const mago2024 = {
  id: 9, rules_edition: '2024', settings: {}, ability_scores: [],
  classes: [{ id: 1, class_name: 'wizard', level: 1, hit_die: 6 }],
} as unknown as CharacterFull

const slot = (level: number) => ({ id: level, level, total: 2, used: 0, available: 2, is_pact: false })
const incantesimo = (id: number, name: string, classId: number, prepared: boolean, book: boolean) => ({
  id, name, level: 1, class_id: classId, is_prepared: prepared, always_prepared: false, in_spellbook: book,
})
const magoChierico = {
  id: 10, rules_edition: '2024', settings: {}, ability_scores: [],
  classes: [{ id: 1, class_name: 'wizard', level: 5, hit_die: 6 }, { id: 2, class_name: 'cleric', level: 5, hit_die: 8 }],
  abilities: [{ id: 1, feature_key: 'wizard.memorize_spell', name: 'Memorizzare Incantesimo' }],
  spell_slots: [1, 2, 3, 4, 5].map(slot),
  spells: [incantesimo(1, 'Scudo', 1, true, true), incantesimo(2, 'Sonno', 1, false, true), incantesimo(3, 'Benedizione', 2, true, false)],
} as unknown as CharacterFull

describe('caccia: regola 2024 mago', () => {
  // caccia: {"id": "CB-2716", "fonte": "2024 · Mago · tabella di classe pag. 165; Sottoclasse del Mago · pag. 167", "zona": "regola:2024/wizard", "voce": "edizioni", "copre": ["carta:2024/classes/wizard.md#Sottoclasse del Mago / Wizard Subclass (Mago 3, pag. 167)", "carta:2024/classes/wizard.md#Studioso / Scholar (Mago 2, pag. 166)", "route:/char/:id/xp"]}
  it.fails('la salita di livello di un mago 2024 non annuncia la Tradizione Arcana del 2014 al 2° livello', () => {
    renderWithProviders(createElement(LevelUpModal, { char: mago2024, xpLevel: 2, onClose: vi.fn() }))
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.queryByText(/Tradizione Arcana|Arcane Tradition/)).toBeNull()
  })

  // caccia: {"id": "CB-2717", "fonte": "2024 · Mago · Memorizzare Incantesimo · pag. 167", "zona": "regola:2024/wizard", "voce": "interazione", "copre": ["carta:2024/classes/wizard.md#Memorizzare Incantesimo / Memorize Spell (Mago 5, pag. 167)", "carta:2024/classes/wizard.md#Multiclasse: Mago / Multiclassing: Wizard (Mago, pag. 44)", "route:/char/:id"]}
  it('Memorizzare Incantesimo non propone di togliere un incantesimo preparato da chierico', () => {
    renderWithProviders(createElement(MemorizeSpellPicker, { char: magoChierico, onChange: vi.fn() }))
    const uscita = screen.getByTestId('memorize-out')
    const nomi = Array.from(uscita.querySelectorAll('option')).map((o) => o.textContent)
    expect(nomi).toContain('Scudo')
    expect(nomi).not.toContain('Benedizione')
  })
})

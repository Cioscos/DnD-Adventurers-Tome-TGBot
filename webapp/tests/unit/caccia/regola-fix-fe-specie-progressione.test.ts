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

const pg2024 = (className: string, level: number) => ({
  id: 9, rules_edition: '2024', settings: {}, ability_scores: [],
  classes: [{ id: 1, class_name: className, level, hit_die: 8 }],
}) as unknown as CharacterFull

describe('caccia: correzione fe-specie-progressione', () => {
  // caccia: {"id": "CB-4552", "fonte": "2024 · Stregone · Tabella di classe, Metamagia e Sottoclasse da Stregone · pag. 139-141", "zona": "regola:2024/sorcerer", "voce": "edizioni", "copre": ["carta:2024/classes/sorcerer.md#Metamagia / Metamagic (Stregone 2, pag. 141)", "carta:2024/classes/sorcerer.md#Sottoclasse da Stregone / Sorcerer Subclass (Stregone 3, pag. 141)", "route:/char/:id/xp"]}
  it('la salita di livello di uno stregone 2024 non annuncia la Metamagia del 2014 al 3° livello', () => {
    // 2024: Metamagia al 2°, 10° e 17°; al 3° la sottoclasse, al 5° Ripristino Stregonesco (pag. 139)
    renderWithProviders(createElement(LevelUpModal, { char: pg2024('sorcerer', 2), xpLevel: 3, onClose: vi.fn() }))
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.queryByText(/Metamagic|Metamagia/)).toBeNull()
  })

  // caccia: {"id": "CB-4553", "fonte": "2024 · Barbaro · Tabella di classe, Colpo Brutale · pag. 51-53", "zona": "regola:2024/barbarian", "voce": "edizioni", "copre": ["carta:2024/classes/barbarian.md#Colpo Brutale / Brutal Strike (Barbaro 9, pag. 53)", "carta:2024/classes/barbarian.md#Dono Epico / Epic Boon (Barbaro 19, pag. 53)", "route:/char/:id/xp"]}
  it('la salita di livello di un barbaro 2024 non annuncia il Critico Brutale del 2014', () => {
    // 2024: al 9° Colpo Brutale, non Critico Brutale (pag. 51)
    renderWithProviders(createElement(LevelUpModal, { char: pg2024('barbarian', 8), xpLevel: 9, onClose: vi.fn() }))
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.queryByText(/Brutal Critical/)).toBeNull()
  })
})

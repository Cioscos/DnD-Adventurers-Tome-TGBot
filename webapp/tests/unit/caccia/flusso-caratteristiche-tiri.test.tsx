import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import SavingThrows from '@/pages/SavingThrows'
import { d20Count } from '@/hooks/useD20Roll'

const { getChar, updateSavingThrows } = vi.hoisted(() => ({ getChar: vi.fn(), updateSavingThrows: vi.fn() }))

vi.mock('@/api/client', () => ({
  api: { characters: { get: getChar, updateSavingThrows, rollSavingThrow: vi.fn() } },
  ApiError: class extends Error {},
}))
vi.mock('react-router-dom', async (orig) => ({ ...((await orig()) as Record<string, unknown>), useParams: () => ({ id: '5' }) }))
vi.mock('react-i18next', async (orig) => ({
  ...((await orig()) as Record<string, unknown>), useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }),
}))
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'drag', 'layout'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return {
    m: new Proxy({} as Record<string, unknown>, { get: (cache, tag: string | symbol) => (cache[String(tag)] ??= make(String(tag))) }),
    AnimatePresence: (p: { children?: unknown }) => React.createElement(React.Fragment, null, p.children as never),
  }
})
vi.mock('@/auth/telegram', () => ({ haptic: { light: () => {}, success: () => {}, error: () => {} } }))
vi.mock('@/styles/motion', () => ({ stagger: new Proxy({}, { get: () => 0 }), spring: new Proxy({}, { get: () => ({}) }) }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: vi.fn(), info: vi.fn(), success: vi.fn() }) }))
vi.mock('@/hooks/useReducedMotion', () => ({ useReducedMotion: () => true }))
vi.mock('@/dice/useDiceAnimation', () => ({ useDiceAnimation: () => ({ playAndCollect: vi.fn() }) }))
vi.mock('@/store/diceSettings', () => ({ useDiceSettings: (sel: (s: { animate3d: boolean }) => unknown) => sel({ animate3d: false }) }))
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/Reveal', async () => {
  const React = await import('react')
  const C = (p: { children?: unknown }) => React.createElement('div', null, p.children)
  return { default: { Stagger: C, Item: C } }
})
vi.mock('@/components/ui/DiceIcon', async () => ({ default: () => null }))
vi.mock('@/components/homebrew/HomebrewBreakdownRow', async () => ({ default: () => null }))
vi.mock('@/components/ui/Sheet', async () => ({ default: () => null }))
vi.mock('@/components/RollResultModal', async () => ({ default: () => null }))

const char = {
  id: 5, total_level: 1, heroic_inspiration: false, saving_throws: { strength: false, constitution: false },
  ability_scores: [{ name: 'strength', modifier: 2 }], saves_homebrew_modifiers: {},
}

afterEach(() => { getChar.mockReset(); updateSavingThrows.mockReset() })

describe('caccia: tiri salvezza', () => {
  // caccia: {"id": "CB-255", "fonte": "invariante: due modifiche ravvicinate a competenze diverse restano entrambe", "zona": "flusso:caratteristiche-tiri", "voce": "ripetizione", "copre": ["route:/char/:id/saves", "PATCH /characters/{char_id}/saving_throws"]}
  it('due competenze toccate di seguito non si annullano a vicenda', async () => {
    getChar.mockResolvedValue(char)
    updateSavingThrows.mockReturnValue(new Promise(() => {})) // la prima risposta non è ancora arrivata
    renderWithProviders(<SavingThrows />)
    await screen.findByTestId('pb')
    const interruttori = screen.getAllByLabelText('Proficiency')
    await userEvent.click(interruttori[0]) // Forza
    await userEvent.click(interruttori[2]) // Costituzione
    await waitFor(() => expect(updateSavingThrows).toHaveBeenCalledTimes(2))
    const secondo = updateSavingThrows.mock.calls[1][1] as Record<string, boolean>
    // il server unisce quanto riceve: se la seconda richiesta riporta Forza com'era, la prima modifica va persa
    expect(secondo.strength).not.toBe(false)
    expect(secondo.constitution).toBe(true)
  })
})

describe('caccia: quanti d20 animare', () => {
  // caccia: {"id": "CB-992", "fonte": "2014 · Vantaggio e svantaggio · pag. 173 (più fonti dello stesso tipo contano una volta, i due opposti si annullano)", "zona": "flusso:caratteristiche-tiri", "voce": "interazione", "copre": ["route:/char/:id/skills", "route:/char/:id/stats"]}
  it('il numero di dadi segue la somma di modo scelto e opzioni del tiro', () => {
    const scelta = (...modes: Array<'advantage' | 'disadvantage'>) => ({ options: [], modes }) as never
    expect(d20Count('normal')).toBe(1)
    expect(d20Count('advantage')).toBe(2)
    expect(d20Count('advantage', scelta('advantage'))).toBe(2) // due vantaggi contano una volta: sempre due dadi
    expect(d20Count('advantage', scelta('advantage', 'advantage'))).toBe(2)
    expect(d20Count('advantage', scelta('disadvantage'))).toBe(1) // si annullano
    expect(d20Count('disadvantage', scelta('advantage', 'disadvantage'))).toBe(1)
    expect(d20Count('normal', scelta('disadvantage', 'disadvantage'))).toBe(2)
  })
})

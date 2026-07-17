import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import HeroStatsSection from '@/components/character/HeroStatsSection'
import type { CharacterFull } from '@/types'

const { navigateSpy, diceResultSpy } = vi.hoisted(() => ({
  navigateSpy: vi.fn(),
  diceResultSpy: vi.fn(),
}))

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('react-router-dom', () => ({ useNavigate: () => navigateSpy }))
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
vi.mock('@/components/ui/Surface', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void; children?: unknown }) => React.createElement('div', { onClick: p.onClick }, p.children) }
})
vi.mock('@/components/ui/SectionDivider', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/store/unitSettings', () => ({
  useUnitSettings: (sel: (s: { system: string }) => unknown) => sel({ system: 'imperial' }),
  formatLength: (v: number) => `${v} ft`,
}))
// profBonus is the real @/lib/dnd helper (profBonus(5) === 3).
vi.mock('@/api/client', () => ({ api: { dice: { result: diceResultSpy } } }))
// Il tiro d'iniziativa (fallback random, animate3d disattivata) deve girare
// sincrono nel test — niente DiceAnimationProvider reale in giro.
vi.mock('@/dice/useDiceAnimation', () => ({ useDiceAnimation: () => ({ playAndCollect: vi.fn() }) }))
vi.mock('@/store/diceSettings', () => ({
  useDiceSettings: (sel: (s: { animate3d: boolean }) => unknown) => sel({ animate3d: false }),
}))
vi.mock('@/hooks/useReducedMotion', () => ({ useReducedMotion: () => false }))
// Stessa convenzione di Skills.test.tsx / SavingThrows.test.tsx: stub minimale
// che espone titolo e totale senza trascinarsi dietro ResultDialog/AnimatePresence.
vi.mock('@/components/RollResultModal', async () => {
  const React = await import('react')
  return {
    default: (p: { title: string; result: { total: number }; onClose: () => void }) =>
      React.createElement(
        'div',
        { 'data-testid': 'roll-modal' },
        React.createElement('span', { 'data-testid': 'roll-modal-title' }, p.title),
        React.createElement('span', { 'data-testid': 'roll-total' }, String(p.result.total)),
        React.createElement('button', { onClick: p.onClose }, 'close'),
      ),
  }
})

const char = (over: Partial<CharacterFull> = {}): CharacterFull =>
  ({
    id: 7,
    total_level: 5,
    speed: 30,
    speed_homebrew_modifier: 0,
    ability_scores: [
      { name: 'dexterity', modifier: 2 },
      { name: 'wisdom', modifier: 1 },
    ],
    skills: { perception: true, stealth: 'expert', athletics: true },
    skills_homebrew_modifiers: {},
    saving_throws: { strength: true, constitution: true },
    saves_homebrew_modifiers: {},
    ...over,
  } as unknown as CharacterFull)

function renderHero(c: CharacterFull) {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <HeroStatsSection char={c} />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  navigateSpy.mockReset()
  diceResultSpy.mockReset()
})

describe('HeroStatsSection', () => {
  it('derives initiative, proficiency bonus, passive perception and speed (D&D 5e formulas)', () => {
    renderHero(char())
    // initiative = DEX mod (+2); PB = profBonus(5) = +3
    expect(screen.getByRole('button', { name: 'character.hero.initiative: +2' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'character.skills.prof_bonus: +3' })).toBeInTheDocument()
    // passive perception = 10 + WIS(1) + PB(3, proficient) + 0 = 14
    expect(screen.getByRole('button', { name: 'character.skills.passive_perception: 14' })).toBeInTheDocument()
    // speed = 30 + 0
    expect(screen.getByRole('button', { name: 'character.identity.speed: 30 ft' })).toBeInTheDocument()
  })

  it('does not navigate when the initiative cell is tapped (it rolls instead)', async () => {
    diceResultSpy.mockResolvedValue({ notation: '1d20+2', rolls: [15], total: 17, modifier: 2, label: 'character.hero.initiative' })
    renderHero(char())
    await userEvent.click(screen.getByRole('button', { name: 'character.hero.initiative: +2' }))
    expect(navigateSpy).not.toHaveBeenCalled()
  })

  it('navigates to the relevant sub-page when a non-initiative stat cell is tapped', async () => {
    renderHero(char())
    await userEvent.click(screen.getByRole('button', { name: 'character.skills.prof_bonus: +3' }))
    expect(navigateSpy).toHaveBeenCalledWith('/char/7/class')
    await userEvent.click(screen.getByRole('button', { name: 'character.skills.passive_perception: 14' }))
    expect(navigateSpy).toHaveBeenCalledWith('/char/7/skills')
    await userEvent.click(screen.getByRole('button', { name: 'character.identity.speed: 30 ft' }))
    expect(navigateSpy).toHaveBeenCalledWith('/char/7/identity')
  })

  it('rolls 1d20+DEX and shows the RollResultModal when the initiative cell is tapped', async () => {
    diceResultSpy.mockResolvedValue({ notation: '1d20+2', rolls: [15], total: 17, modifier: 2, label: 'character.hero.initiative' })
    renderHero(char())
    await userEvent.click(screen.getByRole('button', { name: 'character.hero.initiative: +2' }))
    await waitFor(() =>
      expect(diceResultSpy).toHaveBeenCalledWith(
        7,
        expect.objectContaining({
          rolls: [{ kind: 'd20', value: expect.any(Number) }],
          modifier: 2,
        }),
      ),
    )
    expect(await screen.findByTestId('roll-modal-title')).toHaveTextContent('character.hero.initiative')
  })

  it('lists proficient saving throws with their total bonus (mod + PB)', () => {
    renderHero(char())
    // strength save: mod 0 + PB 3 = +3
    expect(screen.getByText('character.ability.strength_short')).toBeInTheDocument()
    expect(screen.getByText('character.ability.constitution_short')).toBeInTheDocument()
  })

  it('counts proficient and expert skills', () => {
    renderHero(char())
    // perception + athletics proficient, stealth expert → total 3
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('shows the empty marker when there are no proficient saves', () => {
    renderHero(char({ saving_throws: {} }))
    expect(screen.getByText('character.hero.none_m')).toBeInTheDocument()
  })
})

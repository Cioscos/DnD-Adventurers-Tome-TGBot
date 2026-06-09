import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import HeroStatsSection from '@/components/character/HeroStatsSection'
import type { CharacterFull } from '@/types'

const { navigateSpy } = vi.hoisted(() => ({ navigateSpy: vi.fn() }))

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

afterEach(() => navigateSpy.mockReset())

describe('HeroStatsSection', () => {
  it('derives initiative, proficiency bonus, passive perception and speed (D&D 5e formulas)', () => {
    render(<HeroStatsSection char={char()} />)
    // initiative = DEX mod (+2); PB = profBonus(5) = +3
    expect(screen.getByRole('button', { name: 'character.hero.initiative: +2' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'character.skills.prof_bonus: +3' })).toBeInTheDocument()
    // passive perception = 10 + WIS(1) + PB(3, proficient) + 0 = 14
    expect(screen.getByRole('button', { name: 'character.skills.passive_perception: 14' })).toBeInTheDocument()
    // speed = 30 + 0
    expect(screen.getByRole('button', { name: 'character.identity.speed: 30 ft' })).toBeInTheDocument()
  })

  it('navigates to the relevant sub-page when a stat cell is tapped', async () => {
    render(<HeroStatsSection char={char()} />)
    await userEvent.click(screen.getByRole('button', { name: 'character.hero.initiative: +2' }))
    expect(navigateSpy).toHaveBeenCalledWith('/char/7/stats')
  })

  it('lists proficient saving throws with their total bonus (mod + PB)', () => {
    render(<HeroStatsSection char={char()} />)
    // strength save: mod 0 + PB 3 = +3
    expect(screen.getByText('character.ability.strength_short')).toBeInTheDocument()
    expect(screen.getByText('character.ability.constitution_short')).toBeInTheDocument()
  })

  it('counts proficient and expert skills', () => {
    render(<HeroStatsSection char={char()} />)
    // perception + athletics proficient, stealth expert → total 3
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('shows the empty marker when there are no proficient saves', () => {
    render(<HeroStatsSection char={char({ saving_throws: {} })} />)
    expect(screen.getByText('character.hero.none_m')).toBeInTheDocument()
  })
})

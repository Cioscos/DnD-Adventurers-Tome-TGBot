import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import HeroScreen from '@/pages/character/HeroScreen'
import type { CharacterFull } from '@/types'

const { rollSpy, rollOptions, empty } = vi.hoisted(() => ({
  rollSpy: vi.fn(),
  rollOptions: vi.fn().mockResolvedValue([]),
  empty: () => ({ default: () => null }),
}))

vi.mock('@/api/client', () => ({ api: { characters: { rollDeathSave: rollSpy, rollOptions } } }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/hooks/useD20Roll', () => ({
  useD20Roll: () => async () => null,
  d20Arg: () => undefined,
}))
vi.mock('@/pages/hp/DeathSaveResultDialog', () => ({ default: () => <div data-testid="death-result" /> }))

vi.mock('@/components/character/HeroStatsSection', empty)
vi.mock('@/components/character/SpellSlotsSummary', empty)
vi.mock('@/components/character/QuickActions', empty)
vi.mock('@/components/character/HpQuickSheet', empty)
vi.mock('@/components/character/HeroLayoutSheet', empty)
vi.mock('@/components/character/YourTurnBanner', empty)
vi.mock('@/components/character/PendingChoicesBadge', empty)
vi.mock('@/components/ui/HeroXPBar', empty)

const base = {
  id: 7,
  class_summary: 'Monaco 5',
  hit_points: 20,
  current_hit_points: 12,
  temp_hp: 0,
  ac: 15,
  encumbrance: 0,
  carry_capacity: 100,
  total_level: 5,
  experience_points: 0,
  ability_scores: [{ name: 'dexterity', value: 18, modifier: 4 }],
} as unknown as CharacterFull

const ROLL = 'character.death_saves.roll'

afterEach(() => rollSpy.mockReset())

describe('HeroScreen', () => {
  it('mostra i PF correnti come numero illuminato e il modificatore prima del punteggio', () => {
    renderWithProviders(<HeroScreen char={base} />)
    expect(screen.getByTestId('hero-hp-current')).toHaveTextContent('12')
    expect(screen.queryByRole('button', { name: ROLL })).not.toBeInTheDocument()
    const tile = screen.getByRole('button', { name: /mod \+4/ })
    expect(tile.textContent!.indexOf('+4')).toBeLessThan(tile.textContent!.indexOf('18'))
  })

  it('a 0 PF permette il tiro contro la morte dall\'hub e ne mostra il risultato', async () => {
    rollSpy.mockResolvedValue({ roll: 12 })
    const dying = { ...base, current_hit_points: 0, death_saves: { successes: 1, failures: 0, stable: false } }
    renderWithProviders(<HeroScreen char={dying} />)
    await userEvent.click(screen.getByRole('button', { name: ROLL }))
    await waitFor(() => expect(rollSpy).toHaveBeenCalledWith(7, undefined))
    expect(rollOptions).toHaveBeenCalledWith(7, { roll: 'death_save' })
    expect(await screen.findByTestId('death-result')).toBeInTheDocument()
  })

  it('a 0 PF da stabile o da morto non propone il tiro', () => {
    const stable = { ...base, current_hit_points: 0, death_saves: { successes: 3, failures: 0, stable: true } }
    const { unmount } = renderWithProviders(<HeroScreen char={stable} />)
    expect(screen.queryByRole('button', { name: ROLL })).not.toBeInTheDocument()
    expect(screen.getByText('character.death_saves.stabilized_badge')).toBeInTheDocument()
    unmount()

    const dead = { ...base, current_hit_points: 0, is_dead: true, death_saves: { successes: 0, failures: 3, stable: false } }
    renderWithProviders(<HeroScreen char={dead} />)
    expect(screen.queryByRole('button', { name: ROLL })).not.toBeInTheDocument()
  })
})

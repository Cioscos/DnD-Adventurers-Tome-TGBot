import { describe, it, expect, vi } from 'vitest'
import type { ReactNode } from 'react'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Extras from '@/pages/Extras'
import HeroScreen from '@/pages/character/HeroScreen'
import type { CharacterFull, Companion } from '@/types'

const { getChar, listComp, activate, deactivate } = vi.hoisted(() => ({
  getChar: vi.fn(), listComp: vi.fn(), activate: vi.fn(), deactivate: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: {
    characters: { get: getChar },
    companions: { list: listComp, activate, deactivate, hp: vi.fn(), attack: vi.fn(), create: vi.fn(), remove: vi.fn() },
  },
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: unknown) { super(`API ${status}`) }
  },
}))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '7' }) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/hooks/useD20Roll', () => ({ useD20Roll: () => vi.fn() }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/components/ui/RollButton', async () => {
  const React = await import('react')
  return { default: (p: { children?: ReactNode }) => React.createElement('button', null, p.children) }
})
vi.mock('@/components/skeletons/ActionsSkeleton', () => ({ default: () => null }))
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { children?: ReactNode }) => React.createElement('div', null, p.children) }
})
// HeroScreen children unrelated to the form view.
vi.mock('@/components/character/SpellSlotsSummary', () => ({ default: () => null }))
vi.mock('@/components/character/HeroStatsSection', () => ({ default: () => null }))
vi.mock('@/components/character/PendingChoicesBadge', () => ({ default: () => null }))
vi.mock('@/components/character/YourTurnBanner', () => ({ default: () => null }))
vi.mock('@/components/character/QuickActions', () => ({ default: () => null }))
vi.mock('@/components/character/HpQuickSheet', () => ({ default: () => null }))
vi.mock('@/components/character/HeroLayoutSheet', () => ({ default: () => null }))

const comp = (over: Partial<Companion>): Companion => ({
  id: 1, character_id: 7, kind: 'familiar', name: 'Gufo', srd_index: 'owl', max_hp: 1, current_hp: 1, temp_hp: 0,
  armor_class: 11, notes: null, is_active: false, created_at: '', down: false,
  statblock: { actions: [{ name: 'Artigli', attack_bonus: 3, damage_dice: '1d1', damage_type: 'slashing' }] },
  ...over,
})
const char = {
  id: 7, classes: [{ id: 1, class_name: 'druid', level: 4, subclass: 'Circle of the Moon' }],
  abilities: [{ id: 1, feature_key: 'druid.wild_shape', uses: 2, max_uses: 2 }],
} as unknown as CharacterFull

describe('Extras page', () => {
  it('renders a familiar and a wild shape; "Attiva forma" calls activate', async () => {
    getChar.mockResolvedValue(char)
    listComp.mockResolvedValue([comp({}), comp({ id: 2, kind: 'wild_shape', name: 'Lupo', max_hp: 11, current_hp: 11 })])
    activate.mockResolvedValue(comp({ id: 2, kind: 'wild_shape', is_active: true }))
    renderWithProviders(<Extras />)
    expect(await screen.findByText('Gufo')).toBeInTheDocument()
    expect(screen.getByText('Lupo')).toBeInTheDocument()
    expect(screen.getAllByText('Artigli')).toHaveLength(2)
    await userEvent.click(screen.getByText('character.extras.activate (2)'))
    await waitFor(() => expect(activate).toHaveBeenCalledWith(7, 2, false))
  })
})

describe('Hero wild shape view', () => {
  it('shows the form HP, AC and the banner when active_form is present', () => {
    const c = {
      id: 7, class_summary: '', current_hit_points: 30, hit_points: 40, temp_hp: 0, ac: 15, ability_scores: [],
      abilities: [], conditions: {}, damage_modifiers: {}, settings: {}, hp_max_homebrew_modifier: 0, encumbrance: 0, carry_capacity: 100,
      active_form: { companion_id: 2, name: 'Lupo', current_hp: 9, max_hp: 11, temp_hp: 0, armor_class: 13 },
    } as unknown as CharacterFull
    renderWithProviders(<HeroScreen char={c} />)
    expect(screen.getByText('9/11')).toBeInTheDocument()
    expect(screen.getByText('13')).toBeInTheDocument()
    expect(screen.getByText('character.extras.in_form_of')).toBeInTheDocument()
    expect(screen.queryByText('30/40')).toBeNull()
  })
})

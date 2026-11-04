import { describe, it, expect, vi } from 'vitest'
import type { ReactNode } from 'react'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Turn from '@/pages/Turn'

const { getChar, turnState, sessionMe } = vi.hoisted(() => ({
  getChar: vi.fn(), turnState: vi.fn(), sessionMe: vi.fn().mockResolvedValue(null),
}))

vi.mock('@/api/client', () => ({
  api: {
    characters: { get: getChar, turnState, tickRound: vi.fn() },
    sessions: { me: sessionMe },
    abilities: { update: vi.fn() },
  },
  ApiError: class ApiError extends Error {},
}))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '7' }) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return {
    ...actual,
    useTranslation: () => ({
      t: (k: string, o?: { damage?: string }) => (o?.damage ? `${k}:${o.damage}` : k),
      i18n: { language: 'it' },
    }),
  }
})
vi.mock('@/pages/spells/useCastFlow', () => ({
  useCastFlow: () => ({ beginCast: vi.fn(), isSpellPending: () => false, elements: null }),
}))
vi.mock('@/hooks/useWeaponAttackFlow', () => ({
  useWeaponAttackFlow: () => ({
    attackWeapon: vi.fn(), attackUnarmed: vi.fn(), isWeaponPending: () => false, isUnarmedPending: false, elements: null,
  }),
}))
vi.mock('@/hooks/useTickRound', () => ({ useTickRound: () => ({ mutate: vi.fn(), isPending: false }) }))
vi.mock('@/components/ui/RollButton', async () => {
  const React = await import('react')
  return { default: (p: { children?: ReactNode }) => React.createElement('button', null, p.children) }
})
vi.mock('@/components/WeaponChoiceRow', () => ({ default: () => null }))
vi.mock('@/components/skeletons/ActionsSkeleton', () => ({ default: () => null }))
vi.mock('@/components/ui/Pressable', async () => {
  const React = await import('react')
  return {
    default: (p: Record<string, unknown>) =>
      React.createElement('button', {
        onClick: p.onClick, 'aria-pressed': p['aria-pressed'], 'aria-expanded': p['aria-expanded'], 'aria-label': p['aria-label'],
      }, p.children as ReactNode),
  }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void; children?: ReactNode }) => React.createElement('button', { onClick: p.onClick }, p.children) }
})
const passthrough = vi.hoisted(() => async () => {
  const React = await import('react')
  return { default: (p: { children?: ReactNode }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/Layout', passthrough)

const char = {
  id: 7, attacks_per_action: 2, items: [], abilities: [], spells: [], classes: [], spellcasting: null,
}

describe('Turn page', () => {
  it('renders the three sections, attacks per action, and resets "used" on new turn', async () => {
    getChar.mockResolvedValue(char)
    renderWithProviders(<Turn />)
    expect(await screen.findByText('character.turn.section_action')).toBeInTheDocument()
    expect(screen.getByText('character.turn.section_bonus_action')).toBeInTheDocument()
    expect(screen.getByText('character.turn.section_reaction')).toBeInTheDocument()
    expect(screen.getByText('character.turn.attacks_per_action')).toBeInTheDocument()

    const toggle = screen.getByLabelText('character.turn.mark_used: character.turn.section_action')
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    await userEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByText('character.turn.new_turn'))
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
  })

  it('keeps the standard actions closed until asked for', async () => {
    getChar.mockResolvedValue(char)
    renderWithProviders(<Turn />)
    expect(await screen.findByText('character.turn.unarmed')).toBeInTheDocument()
    expect(screen.queryByText('Schivata')).not.toBeInTheDocument()
    const rows = screen.getAllByRole('button', { name: 'character.turn.standard_actions' })
    expect(rows[0]).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(rows[0])
    expect(rows[0]).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Schivata')).toBeInTheDocument()
  })

  it('a section marked as used closes, and new turn reopens it', async () => {
    getChar.mockResolvedValue(char)
    renderWithProviders(<Turn />)
    await screen.findByText('character.turn.unarmed')
    const rows = () => screen.getAllByRole('button', { name: 'character.turn.standard_actions' })
    expect(rows()).toHaveLength(2)
    await userEvent.click(screen.getByLabelText('character.turn.mark_used: character.turn.section_action'))
    expect(rows()).toHaveLength(1)
    await userEvent.click(screen.getByText('character.turn.new_turn'))
    expect(rows()).toHaveLength(2)
  })

  it('attacks stay reachable after the action is marked as used', async () => {
    getChar.mockResolvedValue({
      ...char,
      items: [{ id: 1, name: 'Spada', item_type: 'weapon', is_equipped: true }],
    })
    renderWithProviders(<Turn />)
    expect(await screen.findByText('character.turn.section_attacks')).toBeInTheDocument()
    await userEvent.click(screen.getByLabelText('character.turn.mark_used: character.turn.section_action'))
    expect(screen.getByText('Spada')).toBeInTheDocument()
    expect(screen.getByText('character.turn.unarmed')).toBeInTheDocument()
    expect(screen.queryByLabelText('character.turn.mark_used: character.turn.section_attacks')).not.toBeInTheDocument()
  })

  it('shows the unarmed damage die, following the monk level', async () => {
    getChar.mockResolvedValue({ ...char, classes: [{ class_name: 'monk', level: 5 }] })
    renderWithProviders(<Turn />)
    expect(await screen.findByText('character.turn.unarmed_desc:1d6')).toBeInTheDocument()
  })

  it('shows "Fine round" outside an encounter', async () => {
    getChar.mockResolvedValue(char)
    renderWithProviders(<Turn />)
    expect(await screen.findByText('character.turn.end_round')).toBeInTheDocument()
    expect(screen.queryByText('character.conditions.duration.in_encounter')).not.toBeInTheDocument()
  })

  it('hides "Fine round" in an encounter and shows the note', async () => {
    getChar.mockResolvedValue(char)
    sessionMe.mockResolvedValue({ status: 'active', participants: [] })
    turnState.mockResolvedValue({ in_encounter: true, is_my_turn: false, round: 1, session_id: 1 })
    renderWithProviders(<Turn />)
    expect(await screen.findByText('character.conditions.duration.in_encounter')).toBeInTheDocument()
    expect(screen.queryByText('character.turn.end_round')).not.toBeInTheDocument()
  })
})

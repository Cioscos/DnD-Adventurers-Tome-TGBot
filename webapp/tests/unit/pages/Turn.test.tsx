import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { ReactNode } from 'react'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Turn from '@/pages/Turn'

const NEW_BLOCK = {
  action_used: false, bonus_used: false, reaction_used: false, attacks_made: 0, extra_actions: 0,
  once_per_turn: [], spell_slot_cast: false, bonus_spell_cast: false, free_interaction_used: false,
}
// Il server finto tiene lo stato del turno fra una richiesta e l'altra, come quello vero.
const { getChar, turnState, sessionMe, server, turnUse, turnNew } = vi.hoisted(() => {
  const server = { block: {} as Record<string, unknown>, extra: {} as Record<string, unknown> }
  const flag: Record<string, string> = { action: 'action_used', bonus: 'bonus_used', reaction: 'reaction_used', free_interaction: 'free_interaction_used' }
  return {
    server,
    getChar: vi.fn(),
    sessionMe: vi.fn().mockResolvedValue(null),
    turnState: vi.fn(async () => ({
      in_encounter: false, is_my_turn: false, round: null, session_id: null, attacks_allowed: 2, turn: server.block, ...server.extra,
    })),
    turnUse: vi.fn(async (_id: number, slot: string, used: boolean) => {
      if (slot === 'attack') server.block = { ...server.block, attacks_made: (server.block.attacks_made as number) + 1 }
      else server.block = { ...server.block, [flag[slot]]: used }
      return server.block
    }),
    turnNew: vi.fn(async () => (server.block = {})),
  }
})
beforeEach(() => {
  server.block = { ...NEW_BLOCK }
  server.extra = {}
})
vi.mock('@/hooks/useD20Roll', () => ({ useD20Roll: () => vi.fn(), d20Arg: vi.fn() }))

vi.mock('@/api/client', () => ({
  api: {
    characters: { get: getChar, turnState, turnUse, turnNew, tickRound: vi.fn(), rollSkill: vi.fn() },
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
    expect(screen.getByText('character.turn.attacks_made')).toBeInTheDocument()

    const toggle = screen.getByLabelText('character.turn.mark_used: character.turn.section_action')
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    await userEvent.click(toggle)
    await waitFor(() => expect(toggle).toHaveAttribute('aria-pressed', 'true'))
    expect(turnUse).toHaveBeenCalledWith(7, 'action', true)
    await userEvent.click(screen.getByText('character.turn.new_turn'))
    await waitFor(() => expect(toggle).toHaveAttribute('aria-pressed', 'false'))
  })

  it('shows the action as used after a reload, because the state comes from the server', async () => {
    server.block = { ...NEW_BLOCK, bonus_used: true }
    getChar.mockResolvedValue(char)
    renderWithProviders(<Turn />)
    const toggle = await screen.findByLabelText('character.turn.mark_used: character.turn.section_bonus_action')
    await waitFor(() => expect(toggle).toHaveAttribute('aria-pressed', 'true'))
  })

  it('shows an unlimited class feature without a use button', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [{
      id: 5, name: 'Ira', is_passive: false, is_active: true, is_class_feature: true,
      feature_key: 'barbarian.rage', max_uses: null, uses: null, action_type: 'bonus_action', restoration_type: 'long_rest',
    }] })
    renderWithProviders(<Turn />)
    expect(await screen.findByText('Ira (character.abilities.unlimited)')).toBeInTheDocument()
    expect(screen.queryByText('character.turn.use')).not.toBeInTheDocument()
  })

  it('does not call unlimited an active feature that simply has no counter', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [{
      id: 6, name: 'Azione Scaltra', is_passive: false, is_active: true, is_class_feature: true,
      feature_key: 'rogue.cunning_action', max_uses: null, uses: null, action_type: 'bonus_action', restoration_type: 'none',
    }] })
    renderWithProviders(<Turn />)
    expect(await screen.findByText('Azione Scaltra')).toBeInTheDocument()
    expect(screen.queryByText(/character\.abilities\.unlimited/)).not.toBeInTheDocument()
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
    await waitFor(() => expect(rows()).toHaveLength(1))
    await userEvent.click(screen.getByText('character.turn.new_turn'))
    await waitFor(() => expect(rows()).toHaveLength(2))
  })

  it('attacks stay reachable after the action is marked as used', async () => {
    getChar.mockResolvedValue({
      ...char,
      items: [{ id: 1, name: 'Spada', item_type: 'weapon', is_equipped: true }],
    })
    renderWithProviders(<Turn />)
    expect(await screen.findByText('character.turn.section_attacks')).toBeInTheDocument()
    await userEvent.click(screen.getByLabelText('character.turn.mark_used: character.turn.section_action'))
    await waitFor(() => expect(turnUse).toHaveBeenCalled())
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
    server.extra = { in_encounter: true, is_my_turn: false, round: 1, session_id: 1 }
    renderWithProviders(<Turn />)
    expect(await screen.findByText('character.conditions.duration.in_encounter')).toBeInTheDocument()
    expect(screen.queryByText('character.turn.end_round')).not.toBeInTheDocument()
  })
})

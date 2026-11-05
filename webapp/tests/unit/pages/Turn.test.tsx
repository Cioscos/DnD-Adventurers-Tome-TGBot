import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { ReactNode } from 'react'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Turn from '@/pages/Turn'

const NEW_BLOCK = {
  action_used: false, bonus_used: false, reaction_used: false, attacks_made: 0, extra_actions: 0,
  once_per_turn: [], spell_slot_cast: false, bonus_spell_cast: false, free_interaction_used: false,
}
// Il server finto tiene lo stato del turno fra una richiesta e l'altra, come quello vero.
const { getChar, turnState, sessionMe, server, turnUse, turnNew, turnOther, featureUse, endActiveState } = vi.hoisted(() => {
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
    turnOther: vi.fn(async () => (server.block = { ...server.block, once_per_turn: [] })),
    featureUse: vi.fn().mockResolvedValue({ rolls: [], healed: 0, state: null, notes: [] }),
    endActiveState: vi.fn().mockResolvedValue([]),
  }
})
beforeEach(() => {
  server.block = { ...NEW_BLOCK }
  server.extra = {}
})
const { attackUnarmedEffect, rollSkill, updateConditions, hide } = vi.hoisted(() => ({
  attackUnarmedEffect: vi.fn(),
  rollSkill: vi.fn().mockResolvedValue({ die: 10, total: 12, notes: [] }),
  updateConditions: vi.fn().mockResolvedValue({ id: 7 }),
  hide: vi.fn().mockResolvedValue({ id: 7 }),
}))
vi.mock('@/hooks/useD20Roll', () => ({ useD20Roll: () => vi.fn(), d20Arg: vi.fn() }))

vi.mock('@/api/client', () => ({
  api: {
    characters: { get: getChar, turnState, turnUse, turnNew, turnOther, featureUse, endActiveState, tickRound: vi.fn(), rollSkill, updateConditions, hide, rollOptions: vi.fn().mockResolvedValue([]) },
    sessions: { me: sessionMe },
    abilities: { update: vi.fn() },
  },
  ApiError: class ApiError extends Error {
    constructor(public status = 0, public detail: unknown = null) {
      super(`API ${status}`)
    }
  },
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
    attackWeapon: vi.fn(), attackUnarmed: vi.fn(), attackUnarmedEffect, isWeaponPending: () => false, isUnarmedPending: false, elements: null,
  }),
}))
const { toastError } = vi.hoisted(() => ({ toastError: vi.fn() }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: toastError, info: vi.fn(), success: vi.fn() }) }))
vi.mock('@/hooks/useTickRound', () => ({ useTickRound: () => ({ mutate: vi.fn(), isPending: false }) }))
vi.mock('@/components/ui/RollButton', async () => {
  const React = await import('react')
  return { default: (p: { children?: ReactNode; onRoll?: (mode: string) => void }) => React.createElement('button', { onClick: () => p.onRoll?.('normal') }, p.children) }
})
vi.mock('@/components/RollResultModal', () => ({ default: () => null }))
vi.mock('@/components/WeaponChoiceRow', () => ({ default: () => null }))
vi.mock('@/components/skeletons/ActionsSkeleton', () => ({ default: () => null }))
vi.mock('@/components/ui/Pressable', async () => {
  const React = await import('react')
  return {
    default: (p: Record<string, unknown>) =>
      React.createElement('button', {
        onClick: p.onClick, disabled: p.disabled, 'aria-pressed': p['aria-pressed'], 'aria-expanded': p['aria-expanded'], 'aria-label': p['aria-label'],
      }, p.children as ReactNode),
  }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void; disabled?: boolean; children?: ReactNode }) => React.createElement('button', { onClick: p.onClick, disabled: p.disabled }, p.children) }
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

  it('disables every action while incapacitated but keeps the new turn button', async () => {
    getChar.mockResolvedValue({ ...char, computed: { incapacitated: true } })
    renderWithProviders(<Turn />)
    expect(await screen.findByText('character.turn.incapacitated')).toBeInTheDocument()
    expect(screen.getByLabelText('character.turn.mark_used: character.turn.section_action')).toBeDisabled()
    expect(screen.getByText('character.turn.new_turn').closest('button')).toBeEnabled()
  })

  it('turns off the Other section too while incapacitated', async () => {
    getChar.mockResolvedValue({ ...char, computed: { incapacitated: true },
      abilities: [{ id: 1, name: 'Tocco', action_type: 'other', uses: 1, max_uses: 1 }] })
    renderWithProviders(<Turn />)
    await userEvent.click(await screen.findByText('character.turn.section_other'))
    const fieldset = screen.getByTestId('turn-other')
    expect(fieldset).toBeDisabled()
  })

  it('offers grapple and shove on the unarmed strike only in 2024', async () => {
    getChar.mockResolvedValue({ ...char, rules_edition: '2024' })
    const { unmount } = renderWithProviders(<Turn />)
    await userEvent.click(await screen.findByText('character.attack.grapple'))
    expect(attackUnarmedEffect).toHaveBeenCalledWith('grapple')
    expect(screen.getByText('character.attack.shove')).toBeInTheDocument()
    unmount()
    getChar.mockResolvedValue({ ...char, rules_edition: '2014' })
    renderWithProviders(<Turn />)
    await screen.findByText('character.turn.section_action')
    expect(screen.queryByText('character.attack.grapple')).toBeNull()
  })

  it('in 2014 grapple is an Athletics roll that uses up one attack', async () => {
    getChar.mockResolvedValue({ ...char, rules_edition: '2014' })
    renderWithProviders(<Turn />)
    await screen.findByText('character.turn.unarmed')
    await userEvent.click(screen.getAllByRole('button', { name: 'character.turn.standard_actions' })[0])
    const row = screen.getByText('Lottare').closest('li') as HTMLElement
    await userEvent.click(within(row).getByText('character.skills.athletics'))
    await waitFor(() => expect(turnUse).toHaveBeenCalledWith(7, 'attack', true))
    expect(rollSkill.mock.calls[0][1]).toBe('athletics')
  })

  it('stands up from prone and drops prone with the free actions of the Other section', async () => {
    getChar.mockResolvedValue({ ...char, conditions: { prone: true }, computed: { speed: 30 } })
    const { unmount } = renderWithProviders(<Turn />)
    await userEvent.click(await screen.findByText('character.turn.section_other'))
    await userEvent.click(screen.getAllByRole('button', { name: 'character.turn.standard_actions' }).at(-1)!)
    expect(screen.getByText('character.turn.drop_prone').closest('button')).toBeDisabled()
    await userEvent.click(screen.getByText('character.turn.stand_up'))
    await waitFor(() => expect(updateConditions).toHaveBeenCalledWith(7, { prone: false }))
    unmount()
    getChar.mockResolvedValue({ ...char, conditions: {}, computed: { speed: 30 } })
    renderWithProviders(<Turn />)
    await userEvent.click(await screen.findByText('character.turn.section_other'))
    await userEvent.click(screen.getAllByRole('button', { name: 'character.turn.standard_actions' }).at(-1)!)
    expect(screen.getByText('character.turn.stand_up').closest('button')).toBeDisabled()
    await userEvent.click(screen.getByText('character.turn.drop_prone'))
    await waitFor(() => expect(updateConditions).toHaveBeenCalledWith(7, { prone: true }))
  })

  it('in 2024 Hide offers the Invisible state from the total the server saved, a lower one only says so', async () => {
    getChar.mockResolvedValue({ ...char, rules_edition: '2024' })
    hide.mockResolvedValueOnce({ ...char, rules_edition: '2024' })
    const saved = (total: number) => {
      server.block = { ...server.block, last_roll: { roll_id: 'r', roll: 'skill', skill: 'stealth', total } }
    }
    renderWithProviders(<Turn />)
    await screen.findByText('character.turn.unarmed')
    await userEvent.click(screen.getAllByRole('button', { name: 'character.turn.standard_actions' })[0])
    const row = screen.getByText('Nascondersi').closest('li') as HTMLElement
    saved(17)
    await userEvent.click(within(row).getByText('character.skills.stealth'))
    await userEvent.click(await within(row).findByText('character.turn.hide_confirm'))
    await waitFor(() => expect(hide).toHaveBeenCalledWith(7))  // nessun totale dal client
    saved(9)  // un ritiro o un dado in piu cambiano il totale: la UI segue quello del server
    await userEvent.click(within(row).getByText('character.skills.stealth'))
    expect(await within(row).findByText('character.turn.hide_failed')).toBeInTheDocument()
    expect(within(row).queryByText('character.turn.hide_confirm')).toBeNull()
  })

  it('in 2024 Hide is not offered again while the character is already hiding', async () => {
    getChar.mockResolvedValue({ ...char, rules_edition: '2024', hiding_dc: 17 })
    server.block = { ...server.block, last_roll: { roll_id: 'r', roll: 'skill', skill: 'stealth', total: 17 } }
    renderWithProviders(<Turn />)
    await screen.findByText('character.turn.unarmed')
    await userEvent.click(screen.getAllByRole('button', { name: 'character.turn.standard_actions' })[0])
    const row = screen.getByText('Nascondersi').closest('li') as HTMLElement
    await userEvent.click(within(row).getByText('character.skills.stealth'))
    await waitFor(() => expect(rollSkill).toHaveBeenCalled())
    expect(within(row).queryByText('character.turn.hide_confirm')).toBeNull()
  })

  it('in 2024 Influence follows the total the server saved, not the first one the roll showed', async () => {
    getChar.mockResolvedValue({ ...char, rules_edition: '2024' })
    renderWithProviders(<Turn />)
    await screen.findByText('character.turn.unarmed')
    await userEvent.click(screen.getAllByRole('button', { name: 'character.turn.standard_actions' })[0])
    const row = screen.getByText('Influenzare').closest('li') as HTMLElement
    rollSkill.mockResolvedValueOnce({ die: 10, total: 13, notes: [] })
    server.block = { ...server.block, last_roll: { roll_id: 'r', roll: 'skill', skill: 'persuasion', total: 16 } }  // Ispirazione dopo il tiro
    await userEvent.click(within(row).getByText('character.skills.persuasion'))
    expect(await within(row).findByText('character.turn.influence_success')).toBeInTheDocument()
  })

  it('in 2024 Influence has an editable DC of 15 and tells the player how the roll went', async () => {
    getChar.mockResolvedValue({ ...char, rules_edition: '2024' })
    renderWithProviders(<Turn />)
    await screen.findByText('character.turn.unarmed')
    await userEvent.click(screen.getAllByRole('button', { name: 'character.turn.standard_actions' })[0])
    const row = screen.getByText('Influenzare').closest('li') as HTMLElement
    const dc = within(row).getByDisplayValue('15') as HTMLInputElement
    expect(dc.value).toBe('15')
    rollSkill.mockResolvedValueOnce({ die: 10, total: 17, notes: [] })
    server.block = { ...server.block, last_roll: { roll_id: 'r', roll: 'skill', skill: 'persuasion', total: 17 } }
    await userEvent.click(within(row).getByText('character.skills.persuasion'))
    expect(await within(row).findByText('character.turn.influence_success')).toBeInTheDocument()
    await userEvent.clear(dc)
    await userEvent.type(dc, '20')
    expect(await within(row).findByText('character.turn.influence_failure')).toBeInTheDocument()
  })

  it('leaves actions enabled when not incapacitated', async () => {
    getChar.mockResolvedValue({ ...char, computed: { incapacitated: false } })
    renderWithProviders(<Turn />)
    expect(await screen.findByLabelText('character.turn.mark_used: character.turn.section_action')).toBeEnabled()
    expect(screen.queryByText('character.turn.incapacitated')).toBeNull()
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

  it('disables the turn controls while a request is in flight, so taps go out one at a time', async () => {
    getChar.mockResolvedValue(char)
    let release: () => void = () => {}
    turnUse.mockImplementationOnce(() => new Promise((res) => {
      release = () => res({ ...NEW_BLOCK, action_used: true })
    }))
    renderWithProviders(<Turn />)
    const action = await screen.findByLabelText('character.turn.mark_used: character.turn.section_action')
    const bonus = screen.getByLabelText('character.turn.mark_used: character.turn.section_bonus_action')
    await userEvent.click(action)
    await waitFor(() => expect(bonus).toBeDisabled())
    expect(screen.getByText('character.turn.new_turn')).toBeDisabled()
    release()
    await waitFor(() => expect(bonus).not.toBeDisabled())
  })

  it('uses a feature with a real effect through the server, and ends an active state by hand', async () => {
    getChar.mockResolvedValue({
      ...char,
      active_states: [{ key: 'rage', feature_key: 'barbarian.rage', rounds_left: 3, ends_on: ['manual'], data: {} }],
      abilities: [{
        id: 5, name: 'Ira', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
        feature_key: 'barbarian.rage', max_uses: 2, uses: 2, action_type: 'bonus_action', restoration_type: 'long_rest',
      }],
    })
    renderWithProviders(<Turn />)
    await userEvent.click(await screen.findByText('character.turn.use'))
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'barbarian.rage'))
    expect(screen.getByText('character.turn.state_rounds_left')).toBeInTheDocument()
    await userEvent.click(screen.getByText('character.turn.end_state'))
    await waitFor(() => expect(endActiveState).toHaveBeenCalledWith(7, 'rage'))
  })

  it.each([
    ['turn_slot_used', 'character.turn.use_errors.turn_slot_used'],
    ['no_uses', 'character.turn.use_errors.no_uses'],
    ['something_else', 'character.turn.use_errors.default'],
  ])('tells the player why a feature could not be used (%s), never the technical message', async (code, key) => {
    const { ApiError } = await import('@/api/client')
    featureUse.mockRejectedValueOnce(new ApiError(409, { code }))
    getChar.mockResolvedValue({
      ...char,
      abilities: [{
        id: 5, name: 'Ira', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
        feature_key: 'barbarian.rage', max_uses: 2, uses: 2, action_type: 'bonus_action', restoration_type: 'long_rest',
      }],
    })
    toastError.mockClear()
    renderWithProviders(<Turn />)
    await userEvent.click(await screen.findByText('character.turn.use'))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith(key))
  })

  it('names an active state by the saved name, never by its raw key', async () => {
    getChar.mockResolvedValue({
      ...char,
      active_states: [
        { key: 'rage', feature_key: 'barbarian.rage', name: 'Ira', rounds_left: null, ends_on: ['manual'], data: {} },
        { key: 'wild', feature_key: 'druid.wild', rounds_left: null, ends_on: ['manual'], data: {} },
      ],
    })
    renderWithProviders(<Turn />)
    expect(await screen.findByText('Ira')).toBeInTheDocument()
    expect(screen.getByText('character.turn.state_generic')).toBeInTheDocument()
    expect(screen.queryByText('rage')).toBeNull()
    expect(screen.queryByText('wild')).toBeNull()
  })

  describe('another character turn', () => {
    it('clears once-per-turn effects outside an encounter and leaves the reaction alone', async () => {
      turnNew.mockClear()
      server.block = { ...NEW_BLOCK, once_per_turn: ['sneak'], reaction_used: true }
      getChar.mockResolvedValue(char)
      renderWithProviders(<Turn />)
      await userEvent.click(await screen.findByText('character.turn.other_turn'))
      await waitFor(() => expect(turnOther).toHaveBeenCalledWith(7))
      await waitFor(() => expect(screen.queryByText('character.turn.other_turn')).toBeNull())
      expect(turnNew).not.toHaveBeenCalled()
    })

    it('is hidden with nothing to clear and inside an encounter, where turns do it', async () => {
      getChar.mockResolvedValue(char)
      const { unmount } = renderWithProviders(<Turn />)
      await screen.findByText('character.turn.new_turn')
      expect(screen.queryByText('character.turn.other_turn')).toBeNull()
      unmount()
      server.block = { ...NEW_BLOCK, once_per_turn: ['sneak'] }
      server.extra = { in_encounter: true, round: 1 }
      renderWithProviders(<Turn />)
      await screen.findByText('character.turn.new_turn')
      expect(screen.queryByText('character.turn.other_turn')).toBeNull()
    })
  })
})

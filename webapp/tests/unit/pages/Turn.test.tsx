import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { ReactNode } from 'react'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient } from '@tanstack/react-query'
import { renderWithProviders } from '../utils/renderWithProviders'
import Turn from '@/pages/Turn'

const NEW_BLOCK = {
  action_used: false, bonus_used: false, reaction_used: false, attacks_made: 0, action_attacks: 0, extra_actions: 0,
  once_per_turn: [], spell_slot_cast: false, bonus_spell_cast: false, free_interaction_used: false,
}
// Il server finto tiene lo stato del turno fra una richiesta e l'altra, come quello vero.
const { getChar, turnState, sessionMe, server, turnUse, turnNew, turnOther, featureUse, endActiveState, sessionAllies } = vi.hoisted(() => {
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
    sessionAllies: vi.fn().mockResolvedValue([]),
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
    characters: { get: getChar, turnState, turnUse, turnNew, turnOther, featureUse, endActiveState, sessionAllies, tickRound: vi.fn(), rollSkill, updateConditions, hide, rollOptions: vi.fn().mockResolvedValue([]) },
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
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
vi.mock('@/pages/spells/useCastFlow', () => ({
  useCastFlow: () => ({ beginCast: vi.fn(), isSpellPending: () => false, elements: null }),
}))
vi.mock('@/hooks/useWeaponAttackFlow', () => ({
  useWeaponAttackFlow: () => ({
    attackWeapon: vi.fn(), attackUnarmed: vi.fn(), attackUnarmedEffect, isWeaponPending: () => false, isUnarmedPending: false, elements: null,
  }),
}))
const { toastError, toastInfo } = vi.hoisted(() => ({ toastError: vi.fn(), toastInfo: vi.fn() }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: toastError, info: toastInfo, success: vi.fn() }) }))
vi.mock('@/hooks/useTickRound', () => ({ useTickRound: () => ({ mutate: vi.fn(), isPending: false }) }))
vi.mock('@/components/ui/RollButton', async () => {
  const React = await import('react')
  return { default: (p: { children?: ReactNode; onRoll?: (mode: string) => void }) => React.createElement('button', { onClick: () => p.onRoll?.('normal') }, p.children) }
})
vi.mock('@/components/RollResultModal', () => ({ default: () => null }))
vi.mock('@/components/WeaponChoiceRow', () => ({ default: () => null }))
vi.mock('@/components/rules/TargetEffectSheet', async () => {
  const React = await import('react')
  return { default: (p: { effectKey: string }) => React.createElement('div', { 'data-testid': 'target-sheet' }, p.effectKey) }
})
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

  it('rereads the attack limit on a new turn, because an extra action (Haste) changes it', async () => {
    getChar.mockResolvedValue(char)
    renderWithProviders(<Turn />)
    await screen.findByText('character.turn.section_action')
    const reads = turnState.mock.calls.length
    server.extra = { attacks_allowed: 3 }
    await userEvent.click(screen.getByText('character.turn.new_turn'))
    await waitFor(() => expect(turnState.mock.calls.length).toBeGreaterThan(reads))
  })

  it('tells the player what a start-of-turn heal gave and why, and says nothing when there was none', async () => {
    getChar.mockResolvedValue(char)
    renderWithProviders(<Turn />)
    await screen.findByText('character.turn.section_action')
    expect(screen.queryByTestId('start-heal')).not.toBeInTheDocument()
    server.block = { ...NEW_BLOCK, start_heal: [{ feature_key: 'fighter.survivor', name: { it: 'Sopravvissuto', en: 'Survivor' }, amount: 7 }] }
    turnNew.mockImplementationOnce(async () => server.block)
    await userEvent.click(screen.getByText('character.turn.new_turn'))
    expect(await screen.findByTestId('start-heal')).toHaveTextContent('character.turn.start_heal')
    server.block = { ...NEW_BLOCK }
    await userEvent.click(screen.getByText('character.turn.new_turn'))
    await waitFor(() => expect(screen.queryByTestId('start-heal')).not.toBeInTheDocument())
  })

  it('shows the start-of-turn heal that the server kept on the turn, as when the GM moved the encounter on', async () => {
    getChar.mockResolvedValue(char)
    server.block = { ...NEW_BLOCK, start_heal: [{ feature_key: 'fighter.survivor', name: { it: 'Sopravvissuto', en: 'Survivor' }, amount: 5 }] }
    renderWithProviders(<Turn />)
    expect(await screen.findByTestId('start-heal')).toBeInTheDocument()
  })

  it('shows the notice text of a start-of-turn privilege that is not a heal', async () => {
    getChar.mockResolvedValue(char)
    server.block = { ...NEW_BLOCK, start_heal: [{ feature_key: 'fighter.heroic_warrior', name: { it: 'Guerriero Eroico', en: 'Heroic Warrior' }, amount: 0, message: { it: 'Ispirazione Eroica ottenuta', en: 'Heroic Inspiration gained' } }] }
    renderWithProviders(<Turn />)
    expect(await screen.findByTestId('start-heal')).toHaveTextContent(/Ispirazione Eroica ottenuta|Heroic Inspiration gained/)
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

  it('lets an unlimited feature with a real effect be used, and a feature with no counter too', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [
      { id: 5, name: 'Ira', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
        feature_key: 'barbarian.rage', max_uses: null, uses: null, action_type: 'bonus_action', restoration_type: 'long_rest' },
      { id: 6, name: 'Presenza Intimidatoria', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
        feature_key: 'barbarian.intimidating_presence', max_uses: null, uses: null, action_type: 'action', restoration_type: 'none' },
    ] })
    featureUse.mockClear()
    renderWithProviders(<Turn />)
    expect(await screen.findByText('Ira (character.abilities.unlimited)')).toBeInTheDocument()
    expect(screen.getByText('Presenza Intimidatoria')).toBeInTheDocument()
    expect(screen.getAllByText('character.turn.use')).toHaveLength(2)
    await userEvent.click(within(screen.getByText('Presenza Intimidatoria').closest('li') as HTMLElement).getByText('character.turn.use'))
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'barbarian.intimidating_presence'))
  })

  it('refreshes the companions after a feature is used, because Primal Companion creates the beast', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [
      { id: 8, name: 'Compagno Primordiale', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
        feature_key: 'ranger.primal_companion', max_uses: 1, uses: 1, action_type: 'action', restoration_type: 'long_rest' },
    ] })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    renderWithProviders(<Turn />, { client })
    await userEvent.click(within((await screen.findByText(/Compagno Primordiale/)).closest('li') as HTMLElement).getByText('character.turn.use'))
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ['companions', 7] }))
  })

  it('shows the dice a feature rolled when it is used, such as Cutting Words', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [{
      id: 8, name: 'Parole Taglienti', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
      feature_key: 'bard.cutting_words', max_uses: null, uses: null, action_type: 'reaction', restoration_type: 'none',
    }] })
    featureUse.mockResolvedValueOnce({ rolls: [5], healed: 0, state: null, notes: [] })
    toastInfo.mockClear()
    renderWithProviders(<Turn />)
    await userEvent.click(within((await screen.findByText('Parole Taglienti')).closest('li') as HTMLElement).getByText('character.turn.use'))
    await waitFor(() => expect(toastInfo).toHaveBeenCalledWith('character.turn.use_rolled', { description: '5 = 5' }))
  })

  it('says the total of the dice and the full outcome of a ki attack (Water Whip)', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [{
      id: 9, name: "Frusta d'Acqua", is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
      feature_key: 'monk.discipline_water_whip', max_uses: null, uses: null, action_type: 'action', restoration_type: 'none',
    }] })
    featureUse.mockResolvedValueOnce({ rolls: [4, 3, 10], healed: 0, state: null, notes: ['water_whip'] })
    toastInfo.mockClear()
    renderWithProviders(<Turn />)
    await userEvent.click(within((await screen.findByText("Frusta d'Acqua")).closest('li') as HTMLElement).getByText('character.turn.use'))
    await waitFor(() => expect(toastInfo).toHaveBeenCalledWith('character.turn.use_rolled', { description: '4 + 3 + 10 = 17' }))
    expect(toastInfo).toHaveBeenCalledWith('character.turn.use_notes.water_whip')
  })

  it('says nothing about dice when the feature rolled none', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [{
      id: 8, name: 'Controfascino', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
      feature_key: 'bard.countercharm', max_uses: null, uses: null, action_type: 'action', restoration_type: 'none',
    }] })
    toastInfo.mockClear()
    renderWithProviders(<Turn />)
    await userEvent.click(within((await screen.findByText('Controfascino')).closest('li') as HTMLElement).getByText('character.turn.use'))
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'bard.countercharm'))
    expect(toastInfo).not.toHaveBeenCalled()
  })

  describe('Bardic Inspiration goes to an ally of the table (R38)', () => {
    const inspiration = { id: 9, name: 'Ispirazione Bardica', is_passive: false, is_active: true, is_class_feature: true,
      has_on_use: true, gives_to_ally: true, feature_key: 'bard.bardic_inspiration', max_uses: 3, uses: 3,
      action_type: 'bonus_action', restoration_type: 'long_rest' }
    const useIt = async () => userEvent.click(within((await screen.findByText(/Ispirazione Bardica/)).closest('li') as HTMLElement)
      .getByText('character.turn.use'))

    it('asks who gets the die and sends the chosen ally', async () => {
      getChar.mockResolvedValue({ ...char, abilities: [inspiration] })
      sessionAllies.mockResolvedValueOnce([{ id: 31, name: 'Brun' }, { id: 32, name: 'Lia' }])
      featureUse.mockClear()
      renderWithProviders(<Turn />)
      await useIt()
      expect(featureUse).not.toHaveBeenCalled()  // prima si sceglie a chi
      await userEvent.click(await screen.findByText('Lia'))
      await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'bard.bardic_inspiration', 1, { target_character_id: 32 }))
    })

    it('uses it without a target for a creature that has no sheet at the table', async () => {
      getChar.mockResolvedValue({ ...char, abilities: [inspiration] })
      sessionAllies.mockResolvedValueOnce([{ id: 31, name: 'Brun', die: null }])
      featureUse.mockClear()
      renderWithProviders(<Turn />)
      await useIt()
      await userEvent.click(await screen.findByText('character.turn.ally_other'))
      await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'bard.bardic_inspiration'))
    })

    it('uses it straight away when nobody else sits at the table', async () => {
      getChar.mockResolvedValue({ ...char, abilities: [inspiration] })
      sessionAllies.mockResolvedValueOnce([])
      featureUse.mockClear()
      renderWithProviders(<Turn />)
      await useIt()
      await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'bard.bardic_inspiration'))
    })
  })

  it('keeps the use button on at zero uses only when the server says the use is free: extending the rage costs nothing', async () => {
    const rage = { id: 5, name: 'Ira', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
      feature_key: 'barbarian.rage', max_uses: 3, uses: 0, action_type: 'bonus_action', restoration_type: 'long_rest' }
    const state = { key: 'rage', feature_key: 'barbarian.rage', rounds_left: 100 }
    getChar.mockResolvedValue({ ...char, abilities: [rage] })
    const { unmount } = renderWithProviders(<Turn />)
    expect(await screen.findByText('character.turn.no_uses')).toBeDisabled()
    unmount()
    // Un'altra classe (Ira 2014) con lo stato attivo: costa un uso, il server non dichiara l'uso libero e il pulsante resta spento
    getChar.mockResolvedValue({ ...char, abilities: [rage], active_states: [state] })
    const { unmount: unmountOther } = renderWithProviders(<Turn />)
    expect(await screen.findByText('character.turn.no_uses')).toBeDisabled()
    unmountOther()
    getChar.mockResolvedValue({ ...char, abilities: [{ ...rage, free_use: true }], active_states: [state] })
    featureUse.mockClear()
    renderWithProviders(<Turn />)
    await userEvent.click(await screen.findByText('character.turn.use'))
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'barbarian.rage'))
  })

  it('lets a depleted feature be restored by spending a rage use: the switch and the button stay reachable', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [{
      id: 6, name: 'Presenza Intimidatoria', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
      feature_key: 'barbarian.intimidating_presence', max_uses: 1, uses: 0, action_type: 'bonus_action', restoration_type: 'long_rest',
      use_toggles: [{ key: 'restore', label: { it: 'Ripristina', en: 'Restore' } }],
    }] })
    featureUse.mockClear()
    renderWithProviders(<Turn />)
    await userEvent.click(await screen.findByRole('switch'))
    await userEvent.click(screen.getByText('character.turn.use'))
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'barbarian.intimidating_presence', 1, { restore: true }))
  })

  it('lets a depleted feature that spends another pool be used when the server says it is free: Beguiling Magic is restored with Inspiration', async () => {
    const beguiling = { id: 8, name: 'Magia Ammaliante', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
      feature_key: 'bard.beguiling_magic', max_uses: 1, uses: 0, action_type: 'bonus_action', restoration_type: 'long_rest', spends_left: 2, free_use: true }
    getChar.mockResolvedValue({ ...char, abilities: [beguiling] })
    featureUse.mockClear()
    const { unmount } = renderWithProviders(<Turn />)
    await userEvent.click(await screen.findByText('character.turn.use'))
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'bard.beguiling_magic'))
    unmount()
    // Senza usi di Ispirazione il pulsante è spento: il server rifiuterebbe comunque
    getChar.mockResolvedValue({ ...char, abilities: [{ ...beguiling, spends_left: 0 }] })
    renderWithProviders(<Turn />)
    expect(await screen.findByText('character.turn.no_uses')).toBeDisabled()
  })

  it('sends the switches chosen when using a feature, such as Frenzy when entering the rage', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [{
      id: 5, name: 'Ira', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
      feature_key: 'barbarian.rage', max_uses: 3, uses: 3, action_type: 'bonus_action', restoration_type: 'long_rest',
      use_toggles: [{ key: 'frenzy', label: { it: 'Frenesia', en: 'Frenzy' } }],
    }] })
    featureUse.mockClear()
    renderWithProviders(<Turn />)
    await userEvent.click(await screen.findByRole('switch'))
    await userEvent.click(screen.getByText('character.turn.use'))
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'barbarian.rage', 1, { frenzy: true }))
    featureUse.mockClear()
    await userEvent.click(screen.getByRole('switch'))  // spenta di nuovo
    await userEvent.click(screen.getByText('character.turn.use'))
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'barbarian.rage', 1, { frenzy: false }))
  })

  it('asks for the skill before using Knowledge of the Ages and sends it in the params', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [{
      id: 8, name: 'Conoscenze Secolari', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
      feature_key: 'cleric.knowledge_of_the_ages', max_uses: null, uses: null, action_type: 'action', restoration_type: 'none',
      use_choices: [{ key: 'skill', label: { it: 'Abilità', en: 'Skill' }, options: [
        { key: 'arcana', label: { it: 'Arcana', en: 'Arcana' } }, { key: 'stealth', label: { it: 'Furtività', en: 'Stealth' } }] }],
    }] })
    featureUse.mockClear()
    renderWithProviders(<Turn />)
    const use = (await screen.findByText('character.turn.use')).closest('button') as HTMLButtonElement
    expect(use).toBeDisabled()  // senza scelta non si usa
    await userEvent.click(screen.getByText('character.turn.choose'))
    await userEvent.click(await screen.findByText('Furtività'))
    expect(use).toBeEnabled()
    await userEvent.click(use)
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'cleric.knowledge_of_the_ages', 1, { skill: 'stealth' }))
  })

  it('asks the slot level and the terrain for Primeval Awareness and sends both, then says what it senses', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [{
      id: 14, name: 'Consapevolezza Primordiale', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
      feature_key: 'ranger.primeval_awareness', max_uses: null, uses: null, action_type: 'action', restoration_type: 'none',
      use_toggles: [{ key: 'terrain', label: { it: 'Terreno prescelto', en: 'Favored terrain' } }],
      use_choices: [{ key: 'slot_level', label: { it: 'Livello dello slot', en: 'Slot level' }, options: [
        { key: '1', label: { it: 'Slot di 1° livello', en: 'Level 1 slot' } }, { key: '2', label: { it: 'Slot di 2° livello', en: 'Level 2 slot' } }] }],
    }] })
    featureUse.mockClear().mockResolvedValueOnce({ rolls: [], healed: 0, state: null, notes: ['primeval_awareness'] })
    toastInfo.mockClear()
    renderWithProviders(<Turn />)
    const use = (await screen.findByText('character.turn.use')).closest('button') as HTMLButtonElement
    expect(use).toBeDisabled()  // senza il livello dello slot non si usa
    await userEvent.click(screen.getByText('character.turn.choose'))
    await userEvent.click(await screen.findByText('Slot di 2° livello'))
    await userEvent.click(screen.getByRole('switch'))
    await userEvent.click(use)
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'ranger.primeval_awareness', 1, { terrain: true, slot_level: '2' }))
    expect(toastInfo).toHaveBeenCalledWith('character.turn.use_notes.primeval_awareness')
  })

  it('tells the player that Vanish is the Hide action, and has a text for a refused slot', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [{
      id: 15, name: 'Svanire', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
      feature_key: 'ranger.vanish', max_uses: null, uses: null, action_type: 'bonus_action', restoration_type: 'none',
    }] })
    featureUse.mockClear().mockResolvedValueOnce({ rolls: [], healed: 0, state: null, notes: ['vanish_hide'] })
    toastInfo.mockClear()
    renderWithProviders(<Turn />)
    await userEvent.click(await screen.findByText('character.turn.use'))
    await waitFor(() => expect(toastInfo).toHaveBeenCalledWith('character.turn.use_notes.vanish_hide'))
    const { ApiError } = await import('@/api/client')
    featureUse.mockRejectedValueOnce(new ApiError(409, { code: 'no_slot' }))
    toastError.mockClear()
    await userEvent.click(screen.getByText('character.turn.use'))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('character.turn.use_errors.no_slot'))
  })

  it('asks which bonus action to take with Cunning Action, sends it and tells what it means', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [{
      id: 21, name: 'Azione Scaltra', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
      feature_key: 'rogue.cunning_action', max_uses: null, uses: null, action_type: 'bonus_action', restoration_type: 'none',
      use_choices: [{ key: 'action', label: { it: 'Azione bonus', en: 'Bonus action' }, options: [
        { key: 'dash', label: { it: 'Scatto', en: 'Dash' } }, { key: 'hide', label: { it: 'Nascondersi', en: 'Hide' } }] }],
    }] })
    featureUse.mockClear().mockResolvedValueOnce({ rolls: [], healed: 0, state: null, notes: ['cunning_hide'] })
    toastInfo.mockClear()
    renderWithProviders(<Turn />)
    const use = (await screen.findByText('character.turn.use')).closest('button') as HTMLButtonElement
    expect(use).toBeDisabled()  // senza l'azione scelta non si usa
    await userEvent.click(screen.getByText('character.turn.choose'))
    await userEvent.click(await screen.findByText('Nascondersi'))
    await userEvent.click(use)
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'rogue.cunning_action', 1, { action: 'hide' }))
    expect(toastInfo).toHaveBeenCalledWith('character.turn.use_notes.cunning_hide')
  })

  it('asks the name of the false identity for Infiltration Expertise, sends it and explains a refusal for lack of gold', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [{
      id: 22, name: 'Maestro Infiltrato', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
      feature_key: 'rogue.infiltration_expertise', max_uses: null, uses: null, action_type: 'special', restoration_type: 'none',
      use_texts: [{ key: 'identity', label: { it: "Nome dell'identità falsa", en: 'Name of the false identity' }, max_len: 80 }],
    }] })
    featureUse.mockClear()
    renderWithProviders(<Turn />)
    await userEvent.click(await screen.findByText('character.turn.section_other'))  // un privilegio «special» sta sotto Altro
    const use = (await screen.findByText('character.turn.use')).closest('button') as HTMLButtonElement
    expect(use).toBeDisabled()  // senza il nome non si usa
    await userEvent.type(screen.getByRole('textbox'), '  Marco il mercante ')
    expect(use).toBeEnabled()
    await userEvent.click(use)
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'rogue.infiltration_expertise', 1, { identity: 'Marco il mercante' }))
    const { ApiError } = await import('@/api/client')
    featureUse.mockRejectedValueOnce(new ApiError(409, 'insufficient_funds'))
    toastError.mockClear()
    await userEvent.type(screen.getByRole('textbox'), 'Altro')
    await userEvent.click(screen.getByText('character.turn.use'))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('character.turn.use_errors.insufficient_funds'))
  })

  it('sends only the toggle when the optional spell name of Spell Thief is left empty', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [{
      id: 23, name: 'Ladro di Incantesimi', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
      feature_key: 'rogue.spell_thief', max_uses: 1, uses: 1, action_type: 'reaction', restoration_type: 'long_rest',
      use_toggles: [{ key: 'stolen', label: { it: 'Il TS è fallito', en: 'The save failed' } }],
      use_choices: [{ key: 'spell_level', optional: true, label: { it: 'Livello', en: 'Level' }, options: [{ key: '1', label: { it: '1° livello', en: 'Level 1' } }] }],
      use_texts: [{ key: 'spell', optional: true, label: { it: 'Nome', en: 'Name' }, max_len: 80 }],
    }] })
    featureUse.mockClear()
    renderWithProviders(<Turn />)
    await userEvent.click(await screen.findByText('character.turn.use'))
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'rogue.spell_thief', 1, { stolen: false }))
  })

  it('opens the target sheet for a feature whose use leaves an effect on others (Intimidating Presence)', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [{
      id: 6, name: 'Presenza Intimidatoria', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
      feature_key: 'barbarian.intimidating_presence', max_uses: null, uses: null, action_type: 'action', restoration_type: 'none',
    }] })
    featureUse.mockResolvedValueOnce({ rolls: [], healed: 0, state: null, notes: [], targets: ['barbarian.intimidating_presence'] })
    renderWithProviders(<Turn />)
    await userEvent.click(await screen.findByText('character.turn.use'))
    expect(await screen.findByTestId('target-sheet')).toHaveTextContent('barbarian.intimidating_presence')
  })

  it('does not open the target sheet when the use leaves no effect on others', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [{
      id: 5, name: 'Ira', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
      feature_key: 'barbarian.rage', max_uses: 3, uses: 3, action_type: 'bonus_action', restoration_type: 'long_rest',
    }] })
    featureUse.mockClear()
    renderWithProviders(<Turn />)
    await userEvent.click(await screen.findByText('character.turn.use'))
    await waitFor(() => expect(featureUse).toHaveBeenCalled())
    expect(screen.queryByTestId('target-sheet')).toBeNull()
  })

  it('a surprised barbarian can still press the rage button, everything else stays off (Feral Instinct)', async () => {
    getChar.mockResolvedValue({ ...char, computed: { incapacitated: true, surprised: true, surprise_exit_features: ['barbarian.rage'] },
      abilities: [
        { id: 5, name: 'Ira', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
          feature_key: 'barbarian.rage', max_uses: 3, uses: 3, action_type: 'bonus_action', restoration_type: 'long_rest' },
        { id: 6, name: 'Tocco', action_type: 'bonus_action', uses: 1, max_uses: 1, feature_key: 'x.touch', has_on_use: true },
      ] })
    featureUse.mockClear()
    renderWithProviders(<Turn />)
    const exit = await screen.findByTestId('turn-surprise-exit')
    const use = within(exit).getByText('character.turn.use').closest('button') as HTMLButtonElement
    expect(use).toBeEnabled()
    await userEvent.click(use)
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'barbarian.rage'))
    expect(screen.getByLabelText('character.turn.mark_used: character.turn.section_action')).toBeDisabled()
    expect(screen.getAllByText(/^Ira/)).toHaveLength(1)  // non compare due volte
    const other = screen.getByText('Tocco (1/1)').closest('li') as HTMLElement
    expect(within(other).getByText('character.turn.use').closest('button')).toBeDisabled()
  })

  it('shows no surprise block when the character is not incapacitated', async () => {
    getChar.mockResolvedValue({ ...char, computed: { incapacitated: false, surprise_exit_features: ['barbarian.rage'] }, abilities: [] })
    renderWithProviders(<Turn />)
    await screen.findByText('character.turn.section_action')
    expect(screen.queryByTestId('turn-surprise-exit')).toBeNull()
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

  const pool = (over: Record<string, unknown> = {}) => ({
    ...char,
    abilities: [{
      id: 8, name: 'Imposizione', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
      feature_key: 'paladin.lay_on_hands', max_uses: 10, uses: 4, action_type: 'action', restoration_type: 'long_rest',
      choose_amount: true, max_amount: null, ...over,
    }],
  })

  it('lets the player choose how many uses a pool feature spends, up to the uses left', async () => {
    getChar.mockResolvedValue(pool())
    featureUse.mockClear()
    renderWithProviders(<Turn />)
    const more = await screen.findByLabelText('character.turn.amount_more')
    const less = screen.getByLabelText('character.turn.amount_less')
    expect(screen.getByTestId('use-amount')).toHaveTextContent('1')
    expect(less).toBeDisabled()
    for (let i = 0; i < 6; i++) await userEvent.click(more)
    expect(screen.getByTestId('use-amount')).toHaveTextContent('4')  // mai oltre gli usi rimasti
    expect(more).toBeDisabled()
    await userEvent.click(less)
    await userEvent.click(screen.getByText('character.turn.use'))
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'paladin.lay_on_hands', 3))
  })

  it('starts the selector at the feature minimum and never goes below it (Water Whip, 2 ki)', async () => {
    getChar.mockResolvedValue(pool({ min_amount: 2, max_uses: 5, uses: 5 }))
    featureUse.mockClear()
    renderWithProviders(<Turn />)
    const less = await screen.findByLabelText('character.turn.amount_less')
    expect(screen.getByTestId('use-amount')).toHaveTextContent('2')
    expect(less).toBeDisabled()
    await userEvent.click(screen.getByLabelText('character.turn.amount_more'))
    await userEvent.click(screen.getByText('character.turn.use'))
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'paladin.lay_on_hands', 3))
  })

  it('lets the player choose how many points of the pool a feature without counter spends, from its minimum (Water Whip)', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [{
      id: 9, name: 'Frusta d\'Acqua', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
      feature_key: 'monk.discipline_water_whip', max_uses: null, uses: null, action_type: 'action', restoration_type: 'none',
      choose_amount: true, min_amount: 2, max_amount: null, spends_left: 5,
    }] })
    featureUse.mockClear()
    renderWithProviders(<Turn />)
    const more = await screen.findByLabelText('character.turn.amount_more')
    expect(screen.getByTestId('use-amount')).toHaveTextContent('2')
    for (let i = 0; i < 6; i++) await userEvent.click(more)
    expect(screen.getByTestId('use-amount')).toHaveTextContent('5')  // mai oltre i ki rimasti
    await userEvent.click(screen.getByLabelText('character.turn.amount_less'))
    await userEvent.click(screen.getByText('character.turn.use'))
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'monk.discipline_water_whip', 4))
  })

  it('turns off a feature without counter when its pool has fewer points than its minimum', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [{
      id: 9, name: 'Frusta d\'Acqua', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
      feature_key: 'monk.discipline_water_whip', max_uses: null, uses: null, action_type: 'action', restoration_type: 'none',
      choose_amount: true, min_amount: 2, max_amount: null, spends_left: 1,
    }] })
    renderWithProviders(<Turn />)
    expect(await screen.findByText('character.turn.no_uses')).toBeInTheDocument()
    expect(screen.queryByTestId('use-amount')).toBeNull()
  })

  it('turns off the Use of a feature that needs more uses than are left', async () => {
    getChar.mockResolvedValue(pool({ min_amount: 2, max_uses: 5, uses: 1 }))
    renderWithProviders(<Turn />)
    expect(await screen.findByText('character.turn.no_uses')).toBeInTheDocument()
  })

  it('caps the pool selector at the feature own max_amount', async () => {
    getChar.mockResolvedValue(pool({ max_amount: 2 }))
    renderWithProviders(<Turn />)
    const more = await screen.findByLabelText('character.turn.amount_more')
    for (let i = 0; i < 3; i++) await userEvent.click(more)
    expect(screen.getByTestId('use-amount')).toHaveTextContent('2')
  })

  it('shows the amount selector and the choice together for a pool feature (Lay on Hands: on whom) and sends both', async () => {
    getChar.mockResolvedValue(pool({
      max_uses: 25, uses: 25,
      use_choices: [{ key: 'mode', label: { it: 'Su chi', en: 'On whom' }, options: [
        { key: 'self', label: { it: 'Cura te stesso', en: 'Heal yourself' } },
        { key: 'cure', label: { it: 'Cura malattie', en: 'Cure diseases' } }] }],
    }))
    featureUse.mockClear()
    renderWithProviders(<Turn />)
    const use = (await screen.findByText('character.turn.use')).closest('button') as HTMLButtonElement
    expect(screen.getByTestId('use-amount')).toBeInTheDocument()
    expect(use).toBeDisabled()  // la scelta «su chi» è obbligatoria
    await userEvent.click(screen.getByText('character.turn.choose'))
    await userEvent.click(await screen.findByText('Cura malattie'))
    for (let i = 0; i < 4; i++) await userEvent.click(screen.getByLabelText('character.turn.amount_more'))
    expect(use).toBeEnabled()
    await userEvent.click(use)
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'paladin.lay_on_hands', 5, { mode: 'cure' }))
  })

  it('lets a feature be used without an optional choice (Cleansing Touch on another creature)', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [{
      id: 9, name: 'Tocco Purificatore', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
      feature_key: 'paladin.cleansing_touch', max_uses: 2, uses: 2, action_type: 'action', restoration_type: 'long_rest',
      use_choices: [{ key: 'condition', optional: true, label: { it: 'Condizione da terminare su di te', en: 'Condition to end on you' },
        options: [{ key: 'charmed', label: { it: 'Affascinato', en: 'Charmed' } }] }],
    }] })
    featureUse.mockClear()
    renderWithProviders(<Turn />)
    const use = (await screen.findByText('character.turn.use')).closest('button') as HTMLButtonElement
    expect(use).toBeEnabled()
    await userEvent.click(use)
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'paladin.cleansing_touch', 1, { condition: undefined }))
  })

  const touch = (extra = {}) => ({
    id: 9, name: 'Tocco Purificatore', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
    feature_key: 'paladin.cleansing_touch', max_uses: 2, uses: 2, action_type: 'action', restoration_type: 'long_rest',
    use_choices: [{ key: 'condition', optional: true, label: { it: 'Condizione da terminare su di te', en: 'Condition to end on you' },
      options: [{ key: 'charmed', label: { it: 'Affascinato', en: 'Charmed' } }] }], ...extra,
  })

  it('forgets the choice after a use, so the next use starts with no condition (Cleansing Touch twice)', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [touch()] })
    featureUse.mockClear()
    renderWithProviders(<Turn />)
    await userEvent.click(await screen.findByText('character.turn.choice_none'))
    await userEvent.click(await screen.findByText('Affascinato'))
    await userEvent.click((await screen.findByText('character.turn.use')).closest('button') as HTMLButtonElement)
    await waitFor(() => expect(featureUse).toHaveBeenLastCalledWith(7, 'paladin.cleansing_touch', 1, { condition: 'charmed' }))
    await waitFor(() => expect(screen.getByText('character.turn.choice_none')).toBeInTheDocument())  // di nuovo vuota
    await userEvent.click((await screen.findByText('character.turn.use')).closest('button') as HTMLButtonElement)
    await waitFor(() => expect(featureUse).toHaveBeenCalledTimes(2))
    expect(featureUse.mock.calls[1]).toEqual([7, 'paladin.cleansing_touch', 1, {}])
  })

  it('lets an optional choice be taken off again with the None entry', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [touch()] })
    featureUse.mockClear()
    renderWithProviders(<Turn />)
    await userEvent.click(await screen.findByText('character.turn.choice_none'))
    await userEvent.click(await screen.findByText('Affascinato'))
    await userEvent.click(await screen.findByText('Affascinato'))  // il valore scelto è nel pulsante: riapre l'elenco
    await userEvent.click(await screen.findByText('character.turn.choice_none'))
    await userEvent.click((await screen.findByText('character.turn.use')).closest('button') as HTMLButtonElement)
    await waitFor(() => expect(featureUse).toHaveBeenCalled())
    expect(featureUse.mock.calls[0]).toEqual([7, 'paladin.cleansing_touch', 1, {}])
  })

  describe('Lay on Hands on another creature', () => {
    const lay = () => ({
      id: 10, name: 'Imposizione delle Mani', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
      choose_amount: true, ally_modes: ['other'], feature_key: 'paladin.lay_on_hands', max_uses: 25, uses: 25,
      action_type: 'action', restoration_type: 'long_rest',
      use_choices: [{ key: 'mode', label: { it: 'Su chi', en: 'On whom' }, options: [
        { key: 'self', label: { it: 'Cura PF a te stesso', en: 'Heal yourself' } },
        { key: 'other', label: { it: 'Cura PF a un altro', en: 'Heal another' } },
        { key: 'cure', label: { it: 'Togli condizioni', en: 'Remove conditions' } }] }],
      removal: { count: null, max_targets: 1, ally: true, modes: ['cure'], cost_each: 5,
        conditions: [{ key: 'poisoned', label: { it: 'Avvelenato', en: 'Poisoned' } }], untracked: [{ key: 'disease', label: { it: 'malattia', en: 'disease' } }] },
    })
    const pick = async (label: string) => {
      await userEvent.click(await screen.findByText('character.turn.choose'))
      await userEvent.click(await screen.findByText(label))
    }

    it('asks who gets the heal only for the mode aimed at another creature, and keeps the mode in the params', async () => {
      getChar.mockResolvedValue({ ...char, abilities: [lay()] })
      sessionAllies.mockResolvedValue([{ id: 31, name: 'Brun' }])
      featureUse.mockClear()
      renderWithProviders(<Turn />)
      await pick('Cura PF a un altro')
      await userEvent.click((await screen.findByText('character.turn.use')).closest('button') as HTMLButtonElement)
      expect(featureUse).not.toHaveBeenCalled()  // prima si sceglie a chi
      await userEvent.click(await screen.findByText('Brun'))
      await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'paladin.lay_on_hands', 1, { mode: 'other', target_character_id: 31 }))
    })

    it('the cure mode opens the common removal sheet and sends the same removal body as a spell', async () => {
      getChar.mockResolvedValue({ ...char, abilities: [lay()] })
      sessionAllies.mockResolvedValue([{ id: 31, name: 'Brun' }])
      featureUse.mockClear()
      renderWithProviders(<Turn />)
      await pick('Togli condizioni')
      await userEvent.click((await screen.findByText('character.turn.use')).closest('button') as HTMLButtonElement)
      expect(featureUse).not.toHaveBeenCalled()
      await userEvent.click(await screen.findByText('Avvelenato'))
      await userEvent.click(await screen.findByText('malattia'))
      await userEvent.click(await screen.findByText('character.turn.removal_self'))
      await userEvent.click(await screen.findByText('character.turn.removal_confirm_use'))
      await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'paladin.lay_on_hands', 1,
        { mode: 'cure', removal: { targets: ['self'], conditions: ['poisoned', 'disease'] } }))
    })

    it('does not ask for a target when healing yourself', async () => {
      getChar.mockResolvedValue({ ...char, abilities: [lay()] })
      sessionAllies.mockResolvedValue([{ id: 31, name: 'Brun' }])
      featureUse.mockClear()
      renderWithProviders(<Turn />)
      await pick('Cura PF a te stesso')
      await userEvent.click((await screen.findByText('character.turn.use')).closest('button') as HTMLButtonElement)
      await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'paladin.lay_on_hands', 1, { mode: 'self' }))
    })

    it('says who regained how many HP', async () => {
      getChar.mockResolvedValue({ ...char, abilities: [lay()] })
      sessionAllies.mockResolvedValue([{ id: 31, name: 'Brun' }])
      featureUse.mockResolvedValueOnce({ rolls: [], healed: 0, state: null, notes: [], received: { name: 'Brun', healed: 6 } })
      renderWithProviders(<Turn />)
      await pick('Cura PF a un altro')
      await userEvent.click((await screen.findByText('character.turn.use')).closest('button') as HTMLButtonElement)
      toastInfo.mockClear()
      await userEvent.click(await screen.findByText('Brun'))
      await waitFor(() => expect(toastInfo).toHaveBeenCalledWith('character.turn.use_received'))
    })
  })

  it('shows a catalog feature with uses and no effect of its own as a counter, with no button to spend it (the pool)', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [
      { id: 5, name: 'Incanalare Divinità', is_passive: false, is_active: true, is_class_feature: true, has_on_use: false,
        is_pool: true, feature_key: 'cleric.channel_divinity', max_uses: 2, uses: 2, action_type: 'action', restoration_type: 'short_rest' },
      { id: 7, name: 'Secondo Vento', is_passive: false, is_active: true, is_class_feature: true, has_on_use: false,
        is_pool: false, feature_key: 'fighter.second_wind', max_uses: 1, uses: 1, action_type: 'bonus_action', restoration_type: 'short_rest' },
      { id: 6, name: 'Mio contatore', is_passive: false, is_active: true, is_class_feature: false, has_on_use: false,
        feature_key: null, max_uses: 3, uses: 3, action_type: 'action', restoration_type: 'long_rest' },
    ] })
    renderWithProviders(<Turn />)
    const pool = (await screen.findByText('Incanalare Divinità (2/2)')).closest('li') as HTMLElement
    expect(within(pool).queryByRole('button')).toBeNull()
    // una riga automatica di classe (fuori catalogo) ha la stessa chiave ma non è una riserva: conserva il «Usa»
    expect(within((await screen.findByText('Secondo Vento (1/1)')).closest('li') as HTMLElement).getByText('character.turn.use')).toBeInTheDocument()
    // un'abilità scritta a mano non ha un effetto da chiamare: il contatore resta suo
    expect(within(screen.getByText('Mio contatore (3/3)').closest('li') as HTMLElement).getByText('character.turn.use')).toBeInTheDocument()
  })

  it('turns off the Use of a feature that spends the pool when the pool has no uses left', async () => {
    getChar.mockResolvedValue({ ...char, abilities: [
      { id: 6, name: 'Preservare Vita', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true, use_panel: 'preserve_life',
        spends_left: 0, feature_key: 'cleric.preserve_life', max_uses: null, uses: null, action_type: 'action', restoration_type: 'none' },
    ] })
    renderWithProviders(<Turn />)
    const row = (await screen.findByText('Preservare Vita')).closest('li') as HTMLElement
    expect(within(row).getByRole('button')).toBeDisabled()
    expect(within(row).getByText('character.turn.no_uses')).toBeInTheDocument()
  })

  it('shows no amount selector for an ordinary feature, which keeps spending one use', async () => {
    getChar.mockResolvedValue(pool({ choose_amount: false }))
    featureUse.mockClear()
    renderWithProviders(<Turn />)
    await userEvent.click(await screen.findByText('character.turn.use'))
    expect(screen.queryByTestId('use-amount')).toBeNull()
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'paladin.lay_on_hands'))
  })

  it('names an active state by the saved name, never by its raw key', async () => {
    getChar.mockResolvedValue({
      ...char,
      active_states: [
        { key: 'rage', feature_key: 'barbarian.rage', name: 'Ira', rounds_left: null, ends_on: ['manual'], data: {} },
        { key: 'wild', feature_key: 'druid.wild', name: null, rounds_left: null, ends_on: ['manual'], data: {} },
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

  describe('Guerriero (Task 23)', () => {
    // Azione Impetuosa non è né azione né azione bonus: sta nella sezione «Altro», che si apre a richiesta.
    const openOther = async () => userEvent.click(await screen.findByText('character.turn.section_other'))
    const surge = (over: Record<string, unknown> = {}) => ({
      ...char,
      abilities: [{
        id: 9, name: 'Azione Impetuosa', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
        feature_key: 'fighter.action_surge', max_uses: 1, uses: 1, action_type: 'special', restoration_type: 'short_rest', ...over,
      }],
    })

    it('an extra action from Action Surge keeps the action section open and can really be spent', async () => {
      server.block = { ...NEW_BLOCK, action_used: true, extra_actions: 1 }
      getChar.mockResolvedValue(char)
      renderWithProviders(<Turn />)
      const toggle = await screen.findByLabelText('character.turn.mark_used: character.turn.section_action')
      expect(toggle).toHaveAttribute('aria-pressed', 'false')  // l'azione normale è spesa, ma ne resta una in più
      expect(screen.getByTestId('extra-actions')).toBeInTheDocument()
      turnUse.mockClear()
      await userEvent.click(toggle)
      await waitFor(() => expect(turnUse).toHaveBeenCalledWith(7, 'action', true))
    })

    it('with the action spent and no extra action the section closes, as before', async () => {
      server.block = { ...NEW_BLOCK, action_used: true, extra_actions: 0 }
      getChar.mockResolvedValue(char)
      renderWithProviders(<Turn />)
      expect(await screen.findByLabelText('character.turn.mark_used: character.turn.section_action')).toHaveAttribute('aria-pressed', 'true')
      expect(screen.queryByTestId('extra-actions')).not.toBeInTheDocument()
    })

    it('sends the Arcane Charge choice and says what the server noted', async () => {
      getChar.mockResolvedValue(surge({ use_toggles: [{ key: 'arcane_charge', label: { it: 'Carica Arcana', en: 'Arcane Charge' } }] }))
      featureUse.mockResolvedValueOnce({ rolls: [], healed: 0, state: null, notes: ['arcane_charge'] })
      toastInfo.mockClear()
      renderWithProviders(<Turn />)
      await openOther()
      await userEvent.click(await screen.findByRole('switch'))
      await userEvent.click(screen.getByText('character.turn.use'))
      await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'fighter.action_surge', 1, { arcane_charge: true }))
      await waitFor(() => expect(toastInfo).toHaveBeenCalledWith('character.turn.use_notes.arcane_charge'))
    })

    it('shows the value a maneuver gives to an ally (Rally, Commander Strike) and never writes it anywhere', async () => {
      getChar.mockResolvedValue({ ...char, abilities: [{
        id: 12, name: 'Incoraggiamento', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true,
        feature_key: 'fighter.maneuver_rally', max_uses: null, uses: null, action_type: 'bonus_action', restoration_type: 'none', spends_left: 3,
      }] })
      featureUse.mockResolvedValueOnce({ rolls: [5], healed: 0, state: null, notes: [], given: 7 })
      toastInfo.mockClear()
      renderWithProviders(<Turn />)
      await userEvent.click(within((await screen.findByText('Incoraggiamento')).closest('li') as HTMLElement).getByText('character.turn.use'))
      await waitFor(() => expect(toastInfo).toHaveBeenCalledWith('character.turn.use_given'))
    })

    it.each(['once_per_turn', 'no_attack_left'])('has a text of its own when the server refuses with %s', async (code) => {
      const { ApiError } = await import('@/api/client')
      featureUse.mockRejectedValueOnce(new ApiError(409, { code }))
      getChar.mockResolvedValue(surge())
      toastError.mockClear()
      renderWithProviders(<Turn />)
      await openOther()
      await userEvent.click(await screen.findByText('character.turn.use'))
      await waitFor(() => expect(toastError).toHaveBeenCalledWith(`character.turn.use_errors.${code}`))
    })

    it('opens the Weapon Bond sheet for a feature that uses a panel of its own', async () => {
      getChar.mockResolvedValue({
        ...char, items: [{ id: 3, name: 'Spada del Cavaliere', item_type: 'weapon', is_equipped: false, item_metadata: {} }],
        abilities: [{
          id: 10, name: 'Arma Vincolata', is_passive: false, is_active: true, is_class_feature: true, has_on_use: true, use_panel: 'weapon_bond',
          feature_key: 'fighter.weapon_bond', max_uses: null, uses: null, action_type: 'bonus_action', restoration_type: 'none',
        }],
      })
      featureUse.mockClear()
      renderWithProviders(<Turn />)
      await userEvent.click(await screen.findByText('character.turn.use'))
      expect(await screen.findByText('Spada del Cavaliere')).toBeInTheDocument()
      expect(featureUse).not.toHaveBeenCalled()  // il server lo rifiuterebbe: l'uso passa dal pannello
    })

    it('a new turn reloads the character, because the start of a turn can heal (Survivor)', async () => {
      getChar.mockResolvedValue(char)
      renderWithProviders(<Turn />)
      await screen.findByText('character.turn.new_turn')
      getChar.mockClear()
      await userEvent.click(screen.getByText('character.turn.new_turn'))
      await waitFor(() => expect(getChar).toHaveBeenCalled())
    })
  })
})

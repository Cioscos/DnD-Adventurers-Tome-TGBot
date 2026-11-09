import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import ActiveStatesBar from '@/components/rules/ActiveStatesBar'
import type { CharacterFull } from '@/types'

const { bardicDieAc, featureUse, toastInfo, toastError, endActiveState, notifyMutationError } = vi.hoisted(() => ({
  bardicDieAc: vi.fn(), featureUse: vi.fn(), toastInfo: vi.fn(), toastError: vi.fn(), endActiveState: vi.fn(), notifyMutationError: vi.fn(),
}))
vi.mock('@/api/client', () => ({
  api: { characters: { endActiveState, bardicDieAc, featureUse } },
  ApiError: class ApiError extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))
vi.mock('@/lib/mutationError', () => ({ notifyMutationError }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ info: toastInfo, error: toastError, success: vi.fn() }) }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

const rage = { key: 'rage', feature_key: 'barbarian.rage', rounds_left: 4, ends_on: ['manual'], name: 'Ira' }
const char = (states: unknown[], abilities: unknown[]) => ({ id: 7, active_states: states, abilities } as unknown as CharacterFull)

describe('ActiveStatesBar', () => {
  it('says that returning to the normal form needs the bonus action when it is already spent', async () => {
    const { ApiError } = await import('@/api/client')
    endActiveState.mockRejectedValueOnce(new ApiError(409, { code: 'turn_slot_used' }))
    renderWithProviders(<ActiveStatesBar char={char(
      [{ key: 'wild_shape', feature_key: 'druid.wild_shape', rounds_left: 1200, ends_on: ['manual'], data: {} }], [],
    )} />)
    await userEvent.click(screen.getByText('character.turn.end_state'))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('character.extras.return_bonus_used'))
    expect(notifyMutationError).not.toHaveBeenCalled()
  })

  it('reads the range, duration, aura, flight and start-of-turn numbers a paladin state carries', () => {
    renderWithProviders(<ActiveStatesBar char={char([
      { key: 'divine_sense', feature_key: 'paladin.divine_sense', rounds_left: null, ends_on: ['manual'], data: { range_m: 18, until: 'next_turn_end' } },
      { key: 'avenging_angel', feature_key: 'paladin.avenging_angel', rounds_left: 600, ends_on: ['manual'], data: { radius_m: 9, fly_ft: 60 } },
      { key: 'elder_champion', feature_key: 'paladin.elder_champion', rounds_left: 10, ends_on: ['manual'], data: { start_heal: 10 } },
      { key: 'holy_nimbus', feature_key: 'paladin.holy_nimbus', rounds_left: 10, ends_on: ['manual'], data: { start_damage: 10, radius_m: 9 } },
    ], [])} />)
    expect(screen.getByText(/character\.turn\.state_until_next_turn_end/)).toBeInTheDocument()
    expect(screen.getByText(/character\.turn\.state_fly/)).toBeInTheDocument()
    expect(screen.getByText(/character\.turn\.state_start_heal/)).toBeInTheDocument()
    expect(screen.getByText(/character\.turn\.state_start_damage/)).toBeInTheDocument()
    expect(screen.getAllByText(/character\.turn\.state_radius/).length).toBeGreaterThanOrEqual(3)
  })

  it('does not offer to end a state that only a long rest closes (ward, Overchannel)', () => {
    renderWithProviders(<ActiveStatesBar char={char([
      { key: 'arcane_ward', feature_key: 'wizard.arcane_ward', rounds_left: null, ends_on: ['rest_long'], data: { hp: 5, max: 10, locked: true } },
    ], [])} />)
    expect(screen.queryByText('character.turn.end_state')).not.toBeInTheDocument()
  })

  it('shows the Wish lock roll and the rests left, and does not offer to end it', () => {
    renderWithProviders(<ActiveStatesBar char={char([
      { key: 'greater_divine_intervention', feature_key: 'cleric.divine_intervention', rounds_left: null, ends_on: ['manual'], name: 'Intervento Divino',
        data: { roll: [2, 3], rests_left: 4, locked: true } },
    ], [])} />)
    expect(screen.getByText(/character\.turn\.wish_lock/)).toBeInTheDocument()
    expect(screen.queryByText('character.turn.end_state')).not.toBeInTheDocument()
  })

  it('lists under a state the features that act on others, with their text', () => {
    renderWithProviders(<ActiveStatesBar char={char(
      [{ ...rage, data: { others: ['barbarian.totem_wolf', 'barbarian.gone'] } }],
      [{ id: 1, name: 'Ira', feature_key: 'barbarian.rage' },
        { id: 2, name: 'Lupo (Spirito Totemico)', feature_key: 'barbarian.totem_wolf', description: 'Gli alleati hanno vantaggio.' }],
    )} />)
    expect(screen.getByText('Lupo (Spirito Totemico): Gli alleati hanno vantaggio.')).toBeInTheDocument()
  })

  it('shows the size of the die a state carries, such as Bardic Inspiration', () => {
    renderWithProviders(<ActiveStatesBar char={char(
      [{ key: 'bardic_inspiration', feature_key: 'bard.bardic_inspiration', rounds_left: 100, ends_on: ['manual'], data: { die: 8 } }],
      [{ id: 1, name: 'Ispirazione Bardica', feature_key: 'bard.bardic_inspiration' }],
    )} />)
    expect(screen.getByText('d8')).toBeInTheDocument()
  })

  it('hides the internal markers a feature keeps for itself (Song of Rest received)', () => {
    renderWithProviders(<ActiveStatesBar char={char(
      [{ key: 'song_of_rest_received', feature_key: 'bard.song_of_rest', rounds_left: null, ends_on: ['rest_short'], name: 'Canto di Riposo', data: { internal: true } }],
      [],
    )} />)
    expect(screen.queryByText('Canto di Riposo')).not.toBeInTheDocument()
    expect(screen.queryByText('character.turn.end_state')).not.toBeInTheDocument()
  })

  it('adds the die of Combat Inspiration to the armor class as a reaction and says the value', async () => {
    bardicDieAc.mockResolvedValue({ die: 6, roll: 4 })
    renderWithProviders(<ActiveStatesBar char={char(
      [{ key: 'bardic_die', feature_key: 'bard.bardic_inspiration', rounds_left: 100, ends_on: ['manual'], name: 'Ispirazione Bardica', data: { die: 6, combat: true } }],
      [],
    )} />)
    await userEvent.click(screen.getByText('character.turn.bardic_die_ac'))
    await waitFor(() => expect(bardicDieAc).toHaveBeenCalledWith(7))
    await waitFor(() => expect(toastInfo).toHaveBeenCalledWith('character.turn.bardic_die_ac_result', { description: '+4' }))
  })

  it('names the received die in the language of the viewer, not the bard one', () => {
    renderWithProviders(<ActiveStatesBar char={char(
      [{ key: 'bardic_die', feature_key: 'bard.bardic_inspiration', rounds_left: 100, ends_on: ['manual'], name: 'Ispirazione Bardica', data: { die: 6 } }],
      [],
    )} />)
    expect(screen.getByText('character.turn.bardic_die_name')).toBeInTheDocument()
    expect(screen.queryByText('Ispirazione Bardica')).not.toBeInTheDocument()
  })

  it('offers no armor class use for a die without Combat Inspiration', () => {
    renderWithProviders(<ActiveStatesBar char={char(
      [{ key: 'bardic_die', feature_key: 'bard.bardic_inspiration', rounds_left: 100, ends_on: ['manual'], name: 'Ispirazione Bardica', data: { die: 6 } }],
      [],
    )} />)
    expect(screen.queryByText('character.turn.bardic_die_ac')).not.toBeInTheDocument()
  })

  it('shows nothing extra for a state without effects on others', () => {
    renderWithProviders(<ActiveStatesBar char={char([{ ...rage, data: {} }], [{ id: 1, name: 'Ira', feature_key: 'barbarian.rage' }])} />)
    expect(screen.getByText('Ira')).toBeInTheDocument()
    expect(screen.queryByText(/:/)).not.toBeInTheDocument()
  })

  it('shows the DC, the challenge rating and the fixed bonus a state carries (Turn Undead, Radiance of the Dawn)', () => {
    renderWithProviders(<ActiveStatesBar char={char(
      [{ key: 'turn_undead', feature_key: 'cleric.turn_undead', rounds_left: 10, ends_on: ['manual'], name: 'Scacciare Non Morti',
         data: { dc: 14, save: 'wisdom', cr: '1', bonus: 6 } }],
      [],
    )} />)
    expect(screen.getByText(/character\.turn\.state_dc/)).toBeInTheDocument()
    expect(screen.getByText(/character\.turn\.state_cr/)).toBeInTheDocument()
    expect(screen.getByText(/character\.turn\.state_bonus/)).toBeInTheDocument()
  })

  it('shows the damage type and the maximised dice of Wrath of the Storm', () => {
    renderWithProviders(<ActiveStatesBar char={char(
      [{ key: 'wrath_of_the_storm', feature_key: 'cleric.wrath_of_the_storm', rounds_left: 1, ends_on: ['manual'], name: 'Collera della Tempesta',
         data: { dc: 12, save: 'dexterity', damage_type: 'thunder', maximized: true } }],
      [],
    )} />)
    expect(screen.getByText(/dmg_thunder/)).toBeInTheDocument()
    expect(screen.getByText(/state_maximized/)).toBeInTheDocument()
  })

  it('tells the outcome of a Divine Intervention', () => {
    renderWithProviders(<ActiveStatesBar char={char(
      [{ key: 'divine_intervention', feature_key: 'cleric.divine_intervention', rounds_left: null, ends_on: ['rest_long', 'manual'],
         name: 'Intervento Divino', data: { roll: 40, level: 12, success: false } }],
      [],
    )} />)
    expect(screen.getByText(/character\.turn\.divine_failure/)).toBeInTheDocument()
  })
})

describe('ActiveStatesBar, rage extension', () => {
  const extendable = { id: 1, name: 'Ira', feature_key: 'barbarian.rage', use_choices: [{ key: 'extend_via', optional: true, options: [] }] }

  it('offers the forced-save extension next to the rage when the server says it can be extended, without the bonus action section', async () => {
    featureUse.mockResolvedValue({})
    renderWithProviders(<ActiveStatesBar char={char([{ ...rage, data: {} }], [extendable])} />)
    await userEvent.click(screen.getByText('character.turn.extend_rage_save'))
    await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'barbarian.rage', 1, { extend_via: 'save' }))
    await waitFor(() => expect(toastInfo).toHaveBeenCalledWith('character.turn.extend_rage_done'))
  })

  it('offers nothing when the server does not list the extension choice (level 15 or another class)', () => {
    renderWithProviders(<ActiveStatesBar char={char([{ ...rage, data: {} }], [{ ...extendable, use_choices: [] }])} />)
    expect(screen.queryByText('character.turn.extend_rage_save')).not.toBeInTheDocument()
  })
})

describe('ActiveStatesBar, wizard states', () => {
  it('reads the ward hit points, the object made and the chosen benefit', () => {
    renderWithProviders(<ActiveStatesBar char={char([
      { key: 'arcane_ward', feature_key: 'wizard.arcane_ward', rounds_left: null, ends_on: ['rest_long'], data: { hp: 7, max: 15 } },
      { key: 'minor_conjuration', feature_key: 'wizard.minor_conjuration', rounds_left: 600, ends_on: ['manual'], data: { object: 'Chiave di ferro' } },
      { key: 'third_eye', feature_key: 'wizard.third_eye', rounds_left: null, ends_on: ['manual'], data: { option: 'darkvision' } },
      { key: 'overchannel', feature_key: 'wizard.overchannel', rounds_left: null, ends_on: ['rest_long'], data: { uses: 2 } },
    ], [])} />)
    expect(screen.getByText(/character\.turn\.state_ward/)).toBeInTheDocument()
    expect(screen.getByText(/Chiave di ferro/)).toBeInTheDocument()
    expect(screen.getByText(/character\.turn\.state_option\.darkvision/)).toBeInTheDocument()
    expect(screen.getByText(/character\.turn\.state_uses/)).toBeInTheDocument()
  })

  it('hides the internal windows the server opens after a cast', () => {
    renderWithProviders(<ActiveStatesBar char={char([
      { key: 'window_enchantment', feature_key: 'wizard.alter_memories', rounds_left: null, ends_on: ['cast'], data: { internal: true } },
    ], [])} />)
    expect(screen.queryByText('character.turn.end_state')).toBeNull()
  })
})

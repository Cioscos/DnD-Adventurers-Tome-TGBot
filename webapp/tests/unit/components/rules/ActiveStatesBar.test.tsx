import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import ActiveStatesBar from '@/components/rules/ActiveStatesBar'
import type { CharacterFull } from '@/types'

const { bardicDieAc, toastInfo, toastError, endActiveState, notifyMutationError } = vi.hoisted(() => ({
  bardicDieAc: vi.fn(), toastInfo: vi.fn(), toastError: vi.fn(), endActiveState: vi.fn(), notifyMutationError: vi.fn(),
}))
vi.mock('@/api/client', () => ({
  api: { characters: { endActiveState, bardicDieAc } },
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

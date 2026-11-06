import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import { RollOptionsHost } from '@/components/rules/RollOptionsPrompt'
import { askRollOptions } from '@/lib/rollOptions'
import { d20Arg } from '@/hooks/useD20Roll'
import RollNotes from '@/components/rules/RollNotes'
import type { RollOption } from '@/api/client'

const { rollOptions, toastWarning } = vi.hoisted(() => ({ rollOptions: vi.fn(), toastWarning: vi.fn() }))
vi.mock('sonner', () => ({ toast: { warning: toastWarning } }))
vi.mock('@/api/client', () => ({ api: { characters: { rollOptions } } }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/hooks/useD20Roll', async (orig) => orig())
vi.mock('@/dice/useDiceAnimation', () => ({ useDiceAnimation: () => ({ playAndCollect: vi.fn() }) }))

const option = (over: Partial<RollOption> = {}): RollOption => ({
  key: 'sneak', phase: 'before', label: 'Applica Attacco Furtivo?', source: 'feature:x', dice: null, bonus: null,
  mode: null, multiplier: null, once_per_turn: false, slot: null, needs: null, requires_input: null,
  input_options: [], auto_fail: false, cost: null, group: null, dice_cost: 0, ...over,
})
const SMITE = option({
  key: 'smite', label: 'Punizione?', requires_input: 'slot', phase: 'after_hit',
  input_options: [{ level: 1, available: 2, dice: '2d8' }, { level: 2, available: 1, dice: '3d8' }],
})
const UNDEAD = option({ key: 'undead', label: 'Non morto?', phase: 'after_hit', needs: 'smite' })

describe('RollNotes', () => {
  it('keeps separate damage apart from the extra dice', () => {
    renderWithProviders(<RollNotes optionResult={{
      keys: ['x'], extra_rolls: [], extra_total: 0, bonus: 0, multiplier: 1, spent: [], separate_rolls: [4, 2], separate_total: 6,
    }} />)
    expect(screen.getByTestId('roll-option-separate')).toHaveTextContent('[4, 2] = 6')
  })
})

describe('askRollOptions', () => {
  beforeEach(() => { rollOptions.mockReset(); toastWarning.mockReset() })

  it('resolves at once, without a prompt, when there are no options', async () => {
    rollOptions.mockResolvedValue([])
    renderWithProviders(<RollOptionsHost />)
    await expect(askRollOptions(1, { roll: 'skill', skill: 'stealth' })).resolves.toEqual({ options: [], option_inputs: {} })
    expect(rollOptions).toHaveBeenCalledWith(1, { roll: 'skill', skill: 'stealth' })
    expect(screen.queryByText('character.roll_options.roll')).toBeNull()
  })

  it('a failed list does not block the roll: the server revalidates anyway', async () => {
    rollOptions.mockRejectedValue(new Error('boom'))
    await expect(askRollOptions(1, { roll: 'skill' })).resolves.toEqual({ options: [], option_inputs: {} })
  })

  it('a server error on the list warns: a confirmation is being skipped', async () => {
    rollOptions.mockRejectedValue(Object.assign(new Error('boom'), { status: 500 }))
    await askRollOptions(1, { roll: 'skill' })
    expect(toastWarning).toHaveBeenCalledTimes(1)
  })

  it('the GM on a player character gets 403: nothing to warn about', async () => {
    rollOptions.mockRejectedValue(Object.assign(new Error('no'), { status: 403 }))
    await askRollOptions(1, { roll: 'initiative' })
    expect(toastWarning).not.toHaveBeenCalled()
  })

  it('only options of the asked phase open the prompt, but after_hit ones ask to defer the damage', async () => {
    rollOptions.mockResolvedValue([option({ phase: 'after_hit' })])
    renderWithProviders(<RollOptionsHost />)
    await expect(askRollOptions(1, { roll: 'attack', item_id: 3 })).resolves.toEqual({
      options: [], option_inputs: {}, defer_damage: true,
    })
    expect(screen.queryByText('Applica Attacco Furtivo?')).toBeNull()
  })

  it('an option that opens an attack outside the Attack action does not count against its limit, like one with its own slot', async () => {
    rollOptions.mockResolvedValue([option({ key: 'agile', label: 'Colpi Agili?', outside_action: true })])
    renderWithProviders(<RollOptionsHost />)
    const answer = askRollOptions(1, { roll: 'attack' })
    await userEvent.click(await screen.findByRole('switch', { name: 'Colpi Agili?' }))
    await userEvent.click(screen.getByText('character.roll_options.roll'))
    await expect(answer).resolves.toMatchObject({ options: ['agile'], own_slot: true })
  })

  it('a spell attack never defers: its damage has its own step', async () => {
    rollOptions.mockResolvedValue([option({ phase: 'after_hit' })])
    await expect(askRollOptions(1, { roll: 'attack', spell_id: 3 })).resolves.toEqual({ options: [], option_inputs: {} })
  })

  it('a chosen before option that opens after-hit effects defers the damage even if none is listed yet', async () => {
    rollOptions.mockResolvedValue([option({ key: 'reckless', label: 'Attacco Irruento?', defers_damage: true }), option({ key: 'other', label: 'Altra?' })])
    renderWithProviders(<RollOptionsHost />)
    const chosen = askRollOptions(1, { roll: 'attack', item_id: 3 })
    await userEvent.click(await screen.findByRole('switch', { name: 'Attacco Irruento?' }))
    await userEvent.click(screen.getByText('character.roll_options.roll'))
    await expect(chosen).resolves.toMatchObject({ options: ['reckless'], defer_damage: true })
    const other = askRollOptions(1, { roll: 'attack', item_id: 3 })
    await userEvent.click(await screen.findByRole('switch', { name: 'Altra?' }))
    await userEvent.click(screen.getByText('character.roll_options.roll'))
    await expect(other).resolves.toEqual({ options: ['other'], option_inputs: {} })
  })

  it('opens with nothing selected: the confirmation is never silent', async () => {
    rollOptions.mockResolvedValue([option()])
    renderWithProviders(<RollOptionsHost />)
    const answer = askRollOptions(1, { roll: 'attack', item_id: 3 })
    await userEvent.click(await screen.findByText('character.roll_options.roll'))
    await expect(answer).resolves.toEqual({ options: [], option_inputs: {} })
  })

  it('returns the chosen keys', async () => {
    rollOptions.mockResolvedValue([option(), option({ key: 'other', label: 'Altra?' })])
    renderWithProviders(<RollOptionsHost />)
    const answer = askRollOptions(1, { roll: 'attack', item_id: 3 })
    await userEvent.click(await screen.findByRole('switch', { name: 'Applica Attacco Furtivo?' }))
    await userEvent.click(screen.getByText('character.roll_options.roll'))
    await expect(answer).resolves.toEqual({ options: ['sneak'], option_inputs: {} })
    await waitFor(() => expect(screen.queryByText('Applica Attacco Furtivo?')).toBeNull())
  })

  it('offers slots with their dice, starts from the lowest and sends the chosen one', async () => {
    rollOptions.mockResolvedValue([SMITE])
    renderWithProviders(<RollOptionsHost />)
    const answer = askRollOptions(1, { roll: 'attack', item_id: 3 }, 'after_hit', {})
    await userEvent.click(await screen.findByRole('switch', { name: 'Punizione?' }))
    const higher = await screen.findByRole('button', { name: /3d8/ })
    await userEvent.click(higher)
    await userEvent.click(screen.getByText('character.roll_options.damage'))
    await expect(answer).resolves.toEqual({ options: ['smite'], option_inputs: { smite: { slot_level: 2 } } })
  })

  it('a saved die is chosen among the saved values and sent as `die`', async () => {
    rollOptions.mockResolvedValue([option({ key: 'portent', label: 'Portento?', saved_dice: [4, 17] })])
    renderWithProviders(<RollOptionsHost />)
    const answer = askRollOptions(1, { roll: 'skill', skill: 'stealth' })
    await userEvent.click(await screen.findByRole('switch', { name: 'Portento?' }))
    await userEvent.click(screen.getByRole('button', { name: '17' }))
    await userEvent.click(screen.getByText('character.roll_options.roll'))
    await expect(answer).resolves.toEqual({ options: ['portent'], option_inputs: { portent: { die: 17 } } })
  })

  it('an option that needs another one is off until that one is on, and falls with it', async () => {
    rollOptions.mockResolvedValue([SMITE, UNDEAD])
    renderWithProviders(<RollOptionsHost />)
    const answer = askRollOptions(1, { roll: 'attack', item_id: 3 }, 'after_hit', {})
    const undead = await screen.findByRole('switch', { name: 'Non morto?' })
    expect(undead).toBeDisabled()
    const smite = screen.getByRole('switch', { name: 'Punizione?' })
    await userEvent.click(smite)
    await waitFor(() => expect(screen.getByRole('switch', { name: 'Non morto?' })).toBeEnabled())
    await userEvent.click(screen.getByRole('switch', { name: 'Non morto?' }))
    await userEvent.click(screen.getByRole('switch', { name: 'Punizione?' }))
    await userEvent.click(screen.getByText('character.roll_options.damage'))
    await expect(answer).resolves.toEqual({ options: [], option_inputs: {} })
  })

  it('only one option of a group stays on', async () => {
    rollOptions.mockResolvedValue([
      option({ key: 'm1', label: 'Manovra 1', group: 'maneuver' }), option({ key: 'm2', label: 'Manovra 2', group: 'maneuver' }),
    ])
    renderWithProviders(<RollOptionsHost />)
    const answer = askRollOptions(1, { roll: 'attack', item_id: 3 })
    await userEvent.click(await screen.findByRole('switch', { name: 'Manovra 1' }))
    await userEvent.click(screen.getByRole('switch', { name: 'Manovra 2' }))
    await userEvent.click(screen.getByText('character.roll_options.roll'))
    await expect(answer).resolves.toEqual({ options: ['m2'], option_inputs: {} })
  })

  it('a group with a larger limit keeps that many options on and drops the oldest', async () => {
    rollOptions.mockResolvedValue([
      option({ key: 'e1', label: 'Effetto 1', group: 'effect', group_max: 2 }), option({ key: 'e2', label: 'Effetto 2', group: 'effect', group_max: 2 }),
      option({ key: 'e3', label: 'Effetto 3', group: 'effect', group_max: 2 }),
    ])
    renderWithProviders(<RollOptionsHost />)
    const answer = askRollOptions(1, { roll: 'attack', item_id: 3 })
    await userEvent.click(await screen.findByRole('switch', { name: 'Effetto 1' }))
    await userEvent.click(screen.getByRole('switch', { name: 'Effetto 2' }))
    expect(screen.getByRole('switch', { name: 'Effetto 1' })).toBeChecked()
    await userEvent.click(screen.getByRole('switch', { name: 'Effetto 3' }))
    await userEvent.click(screen.getByText('character.roll_options.roll'))
    await expect(answer).resolves.toEqual({ options: ['e2', 'e3'], option_inputs: {} })
  })

  it('leaving a group also turns off what depended on the option left', async () => {
    rollOptions.mockResolvedValue([
      option({ key: 'm1', label: 'Manovra 1', group: 'maneuver' }), option({ key: 'm2', label: 'Manovra 2', group: 'maneuver' }),
      option({ key: 'dep', label: 'Dipende', needs: 'm1' }),
    ])
    renderWithProviders(<RollOptionsHost />)
    const answer = askRollOptions(1, { roll: 'attack', item_id: 3 })
    await userEvent.click(await screen.findByRole('switch', { name: 'Manovra 1' }))
    await userEvent.click(screen.getByRole('switch', { name: 'Dipende' }))
    await userEvent.click(screen.getByRole('switch', { name: 'Manovra 2' }))
    await userEvent.click(screen.getByText('character.roll_options.roll'))
    await expect(answer).resolves.toEqual({ options: ['m2'], option_inputs: {} })
  })

  it('an option needing one of another phase, not confirmed, is not offered', async () => {
    rollOptions.mockResolvedValue([
      option({ key: 'reckless', phase: 'before' }), option({ key: 'brutal', phase: 'after_hit', needs: 'reckless' }),
    ])
    renderWithProviders(<RollOptionsHost />)
    await expect(askRollOptions(1, { roll: 'attack', item_id: 3 }, 'after_hit', {})).resolves.toEqual({ options: [], option_inputs: {} })
  })

  it('says how many dice an option takes from the other one', async () => {
    rollOptions.mockResolvedValue([option(), option({ key: 'poison', label: 'Veleno', needs: 'sneak', dice_cost: 2 })])
    renderWithProviders(<RollOptionsHost />)
    const answer = askRollOptions(1, { roll: 'attack', item_id: 3 })
    expect(await screen.findByText('character.roll_options.dice_cost')).toBeInTheDocument()
    await userEvent.click(screen.getByText('character.roll_options.roll'))
    await answer
  })

  it('after the roll the player can say it missed', async () => {
    rollOptions.mockResolvedValue([option({ phase: 'after_hit' })])
    renderWithProviders(<RollOptionsHost />)
    const answer = askRollOptions(1, { roll: 'attack', item_id: 3 }, 'after_hit', {})
    await userEvent.click(await screen.findByText('character.roll_options.miss'))
    await expect(answer).resolves.toMatchObject({ outcome: 'miss' })
  })

  it('offers the inspiration reroll only when asked to', async () => {
    rollOptions.mockResolvedValue([option({ phase: 'after_hit' })])
    renderWithProviders(<RollOptionsHost />)
    const answer = askRollOptions(1, { roll: 'attack', item_id: 3 }, 'after_hit', { canReroll: true })
    await userEvent.click(await screen.findByText('character.roll_options.reroll'))
    await expect(answer).resolves.toMatchObject({ outcome: 'reroll' })
  })
})

describe('d20Arg', () => {
  it('stays the legacy value without options', () => {
    expect(d20Arg('normal', [7], { options: [], option_inputs: {} })).toBe(7)
    expect(d20Arg('advantage', [7, 8], { options: [], option_inputs: {} })).toEqual({ dice: [7, 8], mode: 'advantage' })
  })

  it('carries the options even on a normal roll', () => {
    expect(d20Arg('normal', [7], { options: ['a'], option_inputs: {}, defer_damage: true })).toEqual({
      dice: [7], mode: 'normal', options: ['a'], option_inputs: {}, defer_damage: true,
    })
  })
})

describe('recover options (Expert Divination)', () => {
  beforeEach(() => { rollOptions.mockReset() })

  it('lists the spent slots with the recover wording and sends the chosen level', async () => {
    rollOptions.mockResolvedValue([option({
      key: 'wizard.expert_divination', label: 'Divinazione Esperta', phase: 'before', requires_input: 'recover',
      input_options: [{ level: 1, available: 3, dice: null }, { level: 2, available: 1, dice: null }],
    })])
    renderWithProviders(<RollOptionsHost />)
    const asked = askRollOptions(1, { roll: 'cast', spell_id: 5 })
    await userEvent.click(await screen.findByRole('switch'))
    expect(screen.getAllByText('character.roll_options.slot_recover_choice')).toHaveLength(2)
    await userEvent.click(screen.getAllByText('character.roll_options.slot_recover_choice')[1])
    await userEvent.click(screen.getByText('character.roll_options.roll'))
    await expect(asked).resolves.toEqual({
      options: ['wizard.expert_divination'], option_inputs: { 'wizard.expert_divination': { slot_level: 2 } },
    })
  })
})

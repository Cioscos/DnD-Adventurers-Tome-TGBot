import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import { RollOptionsHost } from '@/components/rules/RollOptionsPrompt'
import { askRollOptions } from '@/lib/rollOptions'
import { d20Arg } from '@/hooks/useD20Roll'
import type { RollOption } from '@/api/client'

const { rollOptions } = vi.hoisted(() => ({ rollOptions: vi.fn() }))
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
  input_options: [], auto_fail: false, cost: null, ...over,
})
const SMITE = option({
  key: 'smite', label: 'Punizione?', requires_input: 'slot', phase: 'after_hit',
  input_options: [{ level: 1, available: 2, dice: '2d8' }, { level: 2, available: 1, dice: '3d8' }],
})
const UNDEAD = option({ key: 'undead', label: 'Non morto?', phase: 'after_hit', needs: 'smite' })

describe('askRollOptions', () => {
  beforeEach(() => { rollOptions.mockReset() })

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

  it('only options of the asked phase open the prompt, but after_hit ones ask to defer the damage', async () => {
    rollOptions.mockResolvedValue([option({ phase: 'after_hit' })])
    renderWithProviders(<RollOptionsHost />)
    await expect(askRollOptions(1, { roll: 'attack', item_id: 3 })).resolves.toEqual({
      options: [], option_inputs: {}, defer_damage: true,
    })
    expect(screen.queryByText('Applica Attacco Furtivo?')).toBeNull()
  })

  it('a spell attack never defers: its damage has its own step', async () => {
    rollOptions.mockResolvedValue([option({ phase: 'after_hit' })])
    await expect(askRollOptions(1, { roll: 'attack', spell_id: 3 })).resolves.toEqual({ options: [], option_inputs: {} })
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

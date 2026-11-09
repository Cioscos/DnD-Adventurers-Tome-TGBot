import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import { RollOptionsHost } from '@/components/rules/RollOptionsPrompt'
import { useAttackRoll } from '@/hooks/useWeaponAttackFlow'
import type { RollOption } from '@/api/client'

const { rollOptions, lastRollOptions, lastRollRefund, attack, attackDamage, attackUnarmed, turnState, toastWarning, toastError, ApiErr } = vi.hoisted(() => ({
  rollOptions: vi.fn(), lastRollOptions: vi.fn(), lastRollRefund: vi.fn(), attack: vi.fn(), attackDamage: vi.fn(),
  attackUnarmed: vi.fn(), turnState: vi.fn(), toastWarning: vi.fn(), toastError: vi.fn(),
  ApiErr: class extends Error {
    status: number
    detail: unknown
    constructor(status: number, detail: unknown) {
      super('api')
      this.status = status
      this.detail = detail
    }
  },
}))
vi.mock('@/api/client', () => ({
  api: { characters: { rollOptions, lastRollOptions, lastRollRefund, turnState }, items: { attack, attackDamage, attackUnarmed } },
  ApiError: ApiErr,
}))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string, o?: { bonus?: string }) => (o?.bonus ? `${k}:${o.bonus}` : k), i18n: { language: 'it' } }) }
})
vi.mock('@/hooks/useD20Roll', async (orig) => ({
  ...(await orig() as object), useD20Roll: () => async () => undefined,
}))
vi.mock('sonner', () => ({ toast: { warning: toastWarning, error: toastError, success: vi.fn(), info: vi.fn() } }))
vi.mock('@/dice/useAnimatedRoll', () => ({ useAnimatedRoll: () => async () => [9] }))

const sneak = {
  key: 'sneak', phase: 'after_hit', label: 'Furtivo?', source: 'feature:x', dice: '2d6', bonus: null, mode: null,
  multiplier: null, once_per_turn: true, slot: null, needs: null, requires_input: null, input_options: [],
  auto_fail: false, cost: null,
} as RollOption
const CHOICE = { grip: 'two', attack_mode: 'thrown' } as const
const hit = { attack_id: 'a1', to_hit_total: 15, to_hit_die: 10, to_hit_bonus: 5, is_critical: false }

function start(inspiration = false) {
  renderWithProviders(<RollOptionsHost />)
  const { result } = renderHook(() => useAttackRoll())
  return result.current.roll(1, 3, 'normal', inspiration, CHOICE)
}

describe('useAttackRoll', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    rollOptions.mockResolvedValue([sneak])
    turnState.mockResolvedValue({ attacks_allowed: 1, turn: { attacks_made: 0, action_attacks: 0 } })
  })

  it('without options the attack call stays the legacy one', async () => {
    rollOptions.mockResolvedValue([])
    attack.mockResolvedValue({ damage_total: 5 })
    await expect(start()).resolves.toEqual({ damage_total: 5 })
    expect(attack).toHaveBeenCalledWith(1, 3, false, undefined, CHOICE)
    expect(rollOptions).toHaveBeenCalledWith(1, { roll: 'attack', item_id: 3, attack_mode: 'thrown', grip: 'two' })
  })

  it('defers the damage and sends the after_hit choices to the second call', async () => {
    attack.mockResolvedValue(hit)
    attackDamage.mockResolvedValue({ damage_total: 12, attack_id: 'a1' })
    const done = start()
    await userEvent.click(await screen.findByRole('switch', { name: 'Furtivo?' }))
    await userEvent.click(screen.getByText('character.roll_options.damage'))
    await expect(done).resolves.toEqual({ damage_total: 12, attack_id: 'a1' })
    expect(attack.mock.calls[0][3]).toMatchObject({ defer_damage: true, options: [] })
    expect(attackDamage).toHaveBeenCalledWith(1, 'a1', expect.objectContaining({ options: ['sneak'] }))
  })

  it('the ranged unarmed throw asks the after-hit options as a ranged attack: no melee option such as Stunning Strike', async () => {
    const thrown = { ...sneak, key: 'throw', phase: 'before', ranged_unarmed: true, slot: null } as RollOption
    rollOptions.mockResolvedValue([thrown, sneak])
    attackUnarmed.mockResolvedValue(hit)
    attackDamage.mockResolvedValue({ damage_total: 7 })
    renderWithProviders(<RollOptionsHost />)
    const { result } = renderHook(() => useAttackRoll())
    const done = result.current.roll(1, null, 'normal', false, undefined, ['throw'])
    await userEvent.click(await screen.findByText('character.roll_options.damage'))
    await done
    // la prima lista serve a riconoscere la scelta; da lì in poi (dopo il colpo) la domanda è quella del lancio
    expect(rollOptions).toHaveBeenLastCalledWith(1, { roll: 'attack', attack_mode: 'thrown' })
  })

  it('a declared miss ends the attack without a damage call', async () => {
    attack.mockResolvedValue(hit)
    const done = start()
    await userEvent.click(await screen.findByText('character.roll_options.miss'))
    await expect(done).resolves.toBeNull()
    expect(attackDamage).not.toHaveBeenCalled()
  })

  it('the miss button also arms the on_miss option (Studied Attacks), without Graze damage', async () => {
    const studied = { ...sneak, key: 'studied', phase: 'after_roll', after: 'miss', once_per_turn: false, on_miss: true } as RollOption
    rollOptions.mockResolvedValue([studied])
    attack.mockResolvedValue(hit)
    lastRollOptions.mockResolvedValue({})
    const done = start()
    await userEvent.click(await screen.findByText('character.roll_options.miss'))
    await expect(done).resolves.toBeNull()
    expect(lastRollOptions).toHaveBeenCalledWith(1, { options: ['studied'], option_inputs: { studied: { declared_only: 1 } }, mode: 'normal' })
    expect(attackDamage).not.toHaveBeenCalled()
  })

  it('a fumble comes back without attack_id: no second step', async () => {
    attack.mockResolvedValue({ is_fumble: true, damage_total: 0 })
    await expect(start()).resolves.toEqual({ is_fumble: true, damage_total: 0 })
    expect(attackDamage).not.toHaveBeenCalled()
  })

  it('the inspiration reroll asks again on the new roll, then no longer offers it', async () => {
    attack.mockResolvedValueOnce(hit).mockResolvedValueOnce({ ...hit, attack_id: 'a2' })
    attackDamage.mockResolvedValue({ damage_total: 1 })
    const done = start(true)
    await userEvent.click(await screen.findByText('character.roll_options.reroll'))
    await act(async () => { await new Promise((r) => setTimeout(r, 0)) })
    expect(attack).toHaveBeenLastCalledWith(1, 3, true, expect.objectContaining({ defer_damage: true }), expect.anything())
    await screen.findByText('character.roll_options.miss')
    expect(screen.queryByText('character.roll_options.reroll')).toBeNull()
    await userEvent.click(screen.getByText('character.roll_options.damage'))
    await done
    expect(attackDamage).toHaveBeenCalledWith(1, 'a2', expect.anything())
  })

  it('a failed second step keeps the base result and warns: the attack is not lost', async () => {
    attack.mockResolvedValue({ ...hit, damage_total: 7 })
    attackDamage.mockRejectedValue(new Error('boom'))
    const done = start()
    await userEvent.click(await screen.findByText('character.roll_options.damage'))
    await expect(done).resolves.toMatchObject({ damage_total: 7 })
    expect(toastWarning).toHaveBeenCalledWith('character.roll_options.damage_failed', expect.anything())
  })

  describe('reroll from the result dialog', () => {
    const reroll = () => {
      renderWithProviders(<RollOptionsHost />)
      const { result } = renderHook(() => useAttackRoll())
      return result.current.reroll(1, 3, CHOICE)
    }

    it('after a natural 1 goes through the second step: after_hit options are asked', async () => {
      attack.mockResolvedValue(hit)
      attackDamage.mockResolvedValue({ damage_total: 12 })
      const done = reroll()
      await userEvent.click(await screen.findByRole('switch', { name: 'Furtivo?' }))
      await userEvent.click(screen.getByText('character.roll_options.damage'))
      await expect(done).resolves.toEqual({ damage_total: 12 })
      expect(attack).toHaveBeenCalledWith(1, 3, true, { dice: [9], mode: 'normal', defer_damage: true }, CHOICE)
      expect(attackDamage).toHaveBeenCalledWith(1, 'a1', expect.objectContaining({ options: ['sneak'] }))
    })

    it('never offers inspiration twice, and a declared miss returns null', async () => {
      attack.mockResolvedValue(hit)
      const done = reroll()
      await screen.findByText('character.roll_options.miss')
      expect(screen.queryByText('character.roll_options.reroll')).toBeNull()
      await userEvent.click(screen.getByText('character.roll_options.miss'))
      await expect(done).resolves.toBeNull()
    })

    it('without after_hit options the call stays the legacy one', async () => {
      rollOptions.mockResolvedValue([])
      attack.mockResolvedValue({ damage_total: 3 })
      await expect(reroll()).resolves.toEqual({ damage_total: 3 })
      expect(attack).toHaveBeenCalledWith(1, 3, true, 9, CHOICE)
    })
  })

  describe('after_roll in the same prompt', () => {
    const luck = { ...sneak, key: 'luck', phase: 'after_roll', label: 'Fortuna?', dice: null, after: 'succeed' } as RollOption
    const add = { ...sneak, key: 'add', phase: 'after_roll', label: 'Somma?', after: 'add', pay_if_success: true } as RollOption
    const again = { ...sneak, key: 'again', phase: 'after_roll', label: 'Ritira?', dice: null, after: 'reroll', mode: 'advantage' } as RollOption

    it('defers even when only after_roll options exist, and the button loops on the updated attack', async () => {
      rollOptions.mockResolvedValue([luck])
      attack.mockResolvedValue(hit)
      lastRollOptions.mockResolvedValue({ attack: { ...hit, forced_hit: true, to_hit_total: 7 } })
      attackDamage.mockResolvedValue({ damage_total: 4 })
      const done = start()
      await userEvent.click(await screen.findByRole('button', { name: /Fortuna\?/ }))
      await act(async () => { await new Promise((r) => setTimeout(r, 0)) })
      expect(attack.mock.calls[0][3]).toMatchObject({ defer_damage: true })
      expect(lastRollOptions).toHaveBeenCalledWith(1, expect.objectContaining({ options: ['luck'] }))
      await userEvent.click(await screen.findByText('character.roll_options.damage'))
      await expect(done).resolves.toEqual({ damage_total: 4 })
    })

    it('a natural 1 offers only what can change it: no damage button, no sums, and the miss shows the fumble', async () => {
      rollOptions.mockResolvedValue([luck, add, sneak])
      attack.mockResolvedValue({ ...hit, to_hit_die: 1, is_fumble: true })
      const done = start()
      await screen.findByRole('button', { name: /Fortuna\?/ })
      expect(screen.queryByRole('button', { name: /Somma\?/ })).toBeNull()
      expect(screen.queryByRole('switch', { name: 'Furtivo?' })).toBeNull()
      expect(screen.queryByText('character.roll_options.damage')).toBeNull()
      await userEvent.click(screen.getByText('character.roll_options.miss'))
      await expect(done).resolves.toMatchObject({ is_fumble: true, attack_id: undefined })
    })

    it('declaring the miss refunds what is paid only on success', async () => {
      rollOptions.mockResolvedValue([add])
      attack.mockResolvedValue(hit)
      lastRollOptions.mockResolvedValue({ attack: { ...hit, to_hit_total: 18 }, refundable: ['add'] })
      lastRollRefund.mockResolvedValue({})
      const done = start()
      await userEvent.click(await screen.findByRole('button', { name: /Somma\?/ }))
      await userEvent.click(await screen.findByText('character.roll_options.miss'))
      await expect(done).resolves.toBeNull()
      expect(lastRollRefund).toHaveBeenCalledWith(1)
    })

    it('the last available pay_if_success option keeps the prompt open: the miss still refunds, no automatic damage', async () => {
      rollOptions.mockResolvedValueOnce([add]).mockResolvedValueOnce([add]).mockResolvedValue([])
      attack.mockResolvedValue(hit)
      lastRollOptions.mockResolvedValue({ attack: { ...hit, to_hit_total: 18 }, refundable: ['add'] })
      lastRollRefund.mockResolvedValue({})
      const done = start()
      await userEvent.click(await screen.findByRole('button', { name: /Somma\?/ }))
      await userEvent.click(await screen.findByText('character.roll_options.miss'))
      await expect(done).resolves.toBeNull()
      expect(attackDamage).not.toHaveBeenCalled()
      expect(lastRollRefund).toHaveBeenCalledWith(1)
    })

    it('a used option is no longer offered on the same attack, and comes back after an inspiration reroll', async () => {
      rollOptions.mockResolvedValue([add, luck])
      attack.mockResolvedValue(hit)
      lastRollOptions.mockResolvedValue({ attack: hit })
      attackDamage.mockResolvedValue({ damage_total: 1 })
      const done = start(true)
      await userEvent.click(await screen.findByRole('button', { name: /Somma\?/ }))
      await screen.findByRole('button', { name: /Fortuna\?/ })
      expect(screen.queryByRole('button', { name: /Somma\?/ })).toBeNull()
      await userEvent.click(screen.getByText('character.roll_options.reroll'))
      await screen.findByRole('button', { name: /Somma\?/ })
      await userEvent.click(screen.getByText('character.roll_options.damage'))
      await done
    })

    it('a refused option keeps the prompt on the same attack and warns', async () => {
      rollOptions.mockResolvedValue([again])
      attack.mockResolvedValue(hit)
      lastRollOptions.mockRejectedValueOnce(new Error('409'))
      const done = start()
      await userEvent.click(await screen.findByRole('button', { name: /Ritira\?/ }))
      await screen.findByRole('button', { name: /Ritira\?/ })
      expect(toastWarning).toHaveBeenCalledWith('character.roll_options.after_roll_failed', expect.anything())
      await userEvent.click(screen.getByText('character.roll_options.miss'))
      await expect(done).resolves.toBeNull()
    })
  })

  it('shows the to-hit bonus with its sign in the second step', async () => {
    attack.mockResolvedValue(hit)
    const done = start()
    await screen.findByText('character.roll_options.summary:+5')
    await userEvent.click(screen.getByText('character.roll_options.miss'))
    await done
  })

  describe('limite di attacchi', () => {
    beforeEach(() => {
      rollOptions.mockResolvedValue([])
      attack.mockResolvedValue({ damage_total: 5 })
      turnState.mockResolvedValue({ attacks_allowed: 1, turn: { attacks_made: 1, action_attacks: 1 } })
    })

    it('asks before rolling and sends the confirmation', async () => {
      const done = start()
      await userEvent.click(await screen.findByText('character.attack.limit_confirm'))
      await done
      expect(attack).toHaveBeenCalledWith(1, 3, false, undefined, { ...CHOICE, confirm_extra_attack: true })
    })

    it('asks the limit of the weapon that attacks: the second attack with the pact weapon is not extra, the third is', async () => {
      turnState.mockImplementation(async (_id: number, itemId?: number) => ({
        attacks_allowed: itemId === 3 ? 2 : 1, turn: { attacks_made: 1, action_attacks: 1 },
      }))
      await start()
      expect(turnState).toHaveBeenCalledWith(1, 3)
      expect(screen.queryByText('character.attack.limit_confirm')).toBeNull()
      expect(attack.mock.calls[0][4]).not.toHaveProperty('confirm_extra_attack')
    })

    it('the third attack with the pact weapon is extra: the question comes back', async () => {
      turnState.mockResolvedValue({ attacks_allowed: 2, turn: { attacks_made: 2, action_attacks: 2 } })
      const third = start()
      expect(await screen.findByText('character.attack.limit_confirm')).toBeInTheDocument()
      await userEvent.click(screen.getByText('character.attack.limit_cancel'))
      await expect(third).resolves.toBeNull()
    })

    it('counts only the attacks of the Attack action: a Frenzy attack made before does not make the next one extra', async () => {
      turnState.mockResolvedValue({ attacks_allowed: 2, turn: { attacks_made: 2, action_attacks: 1 } })
      const done = start()
      await done
      expect(screen.queryByText('character.attack.limit_confirm')).toBeNull()
      expect(attack).toHaveBeenCalled()
    })

    it('an option with its own slot (Frenzy, Retaliation) is not an attack of the Attack action: no limit question', async () => {
      const frenzy = { ...sneak, key: 'barbarian.frenzy_attack', phase: 'before', label: 'Frenesia', slot: 'bonus', once_per_turn: false } as RollOption
      rollOptions.mockResolvedValue([frenzy])
      const done = start()
      await userEvent.click(await screen.findByRole('switch', { name: 'Frenesia' }))
      await userEvent.click(screen.getByText('character.roll_options.roll'))
      await done
      expect(screen.queryByText('character.attack.limit_confirm')).toBeNull()
      expect(attack.mock.calls[0][3]).toMatchObject({ options: ['barbarian.frenzy_attack'] })
      expect(attack.mock.calls[0][3]).not.toHaveProperty('confirm_extra_attack')
      expect(attack.mock.calls[0][4]).not.toHaveProperty('confirm_extra_attack')
    })

    it('still asks when the options chosen have no slot of their own', async () => {
      const plain = { ...sneak, key: 'plain', phase: 'before', label: 'Semplice', slot: null, once_per_turn: false } as RollOption
      rollOptions.mockResolvedValue([plain])
      const done = start()
      await userEvent.click(await screen.findByRole('switch', { name: 'Semplice' }))
      await userEvent.click(screen.getByText('character.roll_options.roll'))
      await userEvent.click(await screen.findByText('character.attack.limit_cancel'))
      await expect(done).resolves.toBeNull()
    })

    it('a preset option (one-tap reaction) skips the prompt and the limit question', async () => {
      const retaliation = { ...sneak, key: 'barbarian.retaliation', phase: 'before', label: 'Ritorsione', slot: 'reaction', once_per_turn: false } as RollOption
      rollOptions.mockResolvedValue([retaliation])
      renderWithProviders(<RollOptionsHost />)
      const { result } = renderHook(() => useAttackRoll())
      await result.current.roll(1, 3, 'normal', false, CHOICE, ['barbarian.retaliation'])
      expect(screen.queryByRole('switch')).toBeNull()
      expect(screen.queryByText('character.attack.limit_confirm')).toBeNull()
      expect(attack.mock.calls[0][3]).toMatchObject({ options: ['barbarian.retaliation'] })
    })

    it('cancelling does not attack', async () => {
      const done = start()
      await userEvent.click(await screen.findByText('character.attack.limit_cancel'))
      await expect(done).resolves.toBeNull()
      expect(attack).not.toHaveBeenCalled()
    })

    it('the extra attack with the other hand does not count', async () => {
      renderWithProviders(<RollOptionsHost />)
      const { result } = renderHook(() => useAttackRoll())
      const choice = { grip: 'one', attack_mode: 'offhand' } as const
      await result.current.roll(1, 3, 'normal', false, choice)
      expect(screen.queryByText('character.attack.limit_confirm')).toBeNull()
      expect(attack).toHaveBeenCalledWith(1, 3, false, undefined, choice)
    })
  })

  it('tells the player when the server refuses an incapacitated attack', async () => {
    rollOptions.mockResolvedValue([])
    attack.mockRejectedValue(new ApiErr(409, { code: 'incapacitated' }))
    await expect(start()).resolves.toBeNull()
    expect(toastError.mock.calls[0][0]).toBe('character.attack.incapacitated')
  })

  it('goes back to the normal attack after the other hand', async () => {
    rollOptions.mockResolvedValue([])
    attack.mockResolvedValue({ attack_id: null })
    const { useWeaponChoices } = await import('@/store/weaponChoiceStore')
    const choice = { grip: 'one', attack_mode: 'offhand' } as const
    useWeaponChoices.getState().setChoice(3, choice)
    const { result } = renderHook(() => useAttackRoll())
    await result.current.roll(1, 3, 'normal', false, choice)
    expect(useWeaponChoices.getState().choices[3].attack_mode).toBe('melee')
  })

  it('grapple and shove go through the limit and reach the server without a d20', async () => {
    attackUnarmed.mockResolvedValue({ effect: 'grapple', save_dc: 13 })
    const { result } = renderHook(() => useAttackRoll())
    await expect(result.current.unarmedEffect(1, 'grapple')).resolves.toEqual({ effect: 'grapple', save_dc: 13 })
    expect(attackUnarmed).toHaveBeenCalledWith(1, false, undefined, { effect: 'grapple' })
  })
})

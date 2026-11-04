import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import { RollOptionsHost } from '@/components/rules/RollOptionsPrompt'
import { useAttackRoll } from '@/hooks/useWeaponAttackFlow'
import type { RollOption } from '@/api/client'

const { rollOptions, attack, attackDamage } = vi.hoisted(() => ({
  rollOptions: vi.fn(), attack: vi.fn(), attackDamage: vi.fn(),
}))
vi.mock('@/api/client', () => ({
  api: { characters: { rollOptions }, items: { attack, attackDamage } },
  ApiError: class extends Error {},
}))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/hooks/useD20Roll', async (orig) => ({
  ...(await orig() as object), useD20Roll: () => async () => undefined,
}))
vi.mock('@/hooks/useAnimatedRoll', () => ({ useAnimatedRoll: () => async () => undefined }))
vi.mock('@/dice/useAnimatedRoll', () => ({ useAnimatedRoll: () => async () => undefined }))

const sneak = {
  key: 'sneak', phase: 'after_hit', label: 'Furtivo?', source: 'feature:x', dice: '2d6', bonus: null, mode: null,
  multiplier: null, once_per_turn: true, slot: null, needs: null, requires_input: null, input_options: [],
  auto_fail: false, cost: null,
} as RollOption
const hit = { attack_id: 'a1', to_hit_total: 15, to_hit_die: 10, to_hit_bonus: 5, is_critical: false }

function start(inspiration = false) {
  renderWithProviders(<RollOptionsHost />)
  const { result } = renderHook(() => useAttackRoll())
  return result.current(1, 3, 'normal', inspiration, { grip: 'one', attack_mode: 'melee' })
}

describe('useAttackRoll', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    rollOptions.mockResolvedValue([sneak])
  })

  it('without options the attack call stays the legacy one', async () => {
    rollOptions.mockResolvedValue([])
    attack.mockResolvedValue({ damage_total: 5 })
    await expect(start()).resolves.toEqual({ damage_total: 5 })
    expect(attack).toHaveBeenCalledWith(1, 3, false, undefined, { grip: 'one', attack_mode: 'melee' })
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

  it('a declared miss ends the attack without a damage call', async () => {
    attack.mockResolvedValue(hit)
    const done = start()
    await userEvent.click(await screen.findByText('character.roll_options.miss'))
    await expect(done).resolves.toBeNull()
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
})

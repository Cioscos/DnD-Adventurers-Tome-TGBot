import { describe, it, expect, vi } from 'vitest'
import type { ReactNode } from 'react'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import CompanionCard from '@/pages/extras/CompanionCard'
import type { Companion } from '@/types'

const { attack } = vi.hoisted(() => ({ attack: vi.fn() }))

vi.mock('@/api/client', () => ({
  api: { companions: { attack, hp: vi.fn() } },
  ApiError: class ApiError extends Error {},
}))
vi.mock('react-i18next', async (orig) => ({
  ...((await orig()) as Record<string, unknown>),
  useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }),
}))
vi.mock('@/hooks/useD20Roll', () => ({ useD20Roll: () => vi.fn().mockResolvedValue([12]) }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: vi.fn(), info: vi.fn(), success: vi.fn() }) }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/lib/rollOptions', async (orig) => ({
  ...((await orig()) as Record<string, unknown>),
  askRollOptions: vi.fn().mockResolvedValue({ options: [], option_inputs: {} }),
  refreshAfterOptions: vi.fn(),
}))
vi.mock('@/components/ui/RollButton', async () => {
  const React = await import('react')
  return { default: (p: { children?: ReactNode; onRoll: (m: string) => void }) =>
    React.createElement('button', { onClick: () => p.onRoll('normal') }, p.children) }
})
vi.mock('@/components/rules/AfterDamageOptions', async () => {
  const React = await import('react')
  return {
    default: (p: { query: { roll: string }; dice: { value: number; sides: number }[]; onResult: (r: unknown) => void }) =>
      React.createElement('button', {
        'data-testid': 'after-damage', 'data-roll': p.query.roll,
        'data-dice': p.dice.map((d) => `${d.value}/d${d.sides}`).join(','),
        onClick: () => p.onResult({ ...result, damage_rolls: [6], damage_total: 8, reroll_dice: [[6, 6]] }),
      }, 'reroll-damage'),
  }
})

const result = {
  to_hit_die: 12, to_hit_bonus: 4, to_hit_total: 16, dice: [12], mode: 'normal', is_critical: false,
  damage_rolls: [2], damage_total: 4, damage_type: 'piercing', reroll_dice: [[6, 2]],
}
const comp = {
  id: 1, character_id: 7, kind: 'familiar', name: 'Gufo', srd_index: 'owl', max_hp: 5, current_hp: 5, temp_hp: 0,
  armor_class: 11, notes: null, is_active: false, created_at: '', down: false,
  statblock: { actions: [{ name: 'Morso', attack_bonus: 4, damage_dice: '1d6+2', damage_type: 'piercing' }] },
} as unknown as Companion

describe('CompanionCard damage reroll', () => {
  it('offers the damage reroll after an attack, with the dice the server knows, and shows the new damage', async () => {
    attack.mockResolvedValue(result)
    renderWithProviders(<CompanionCard charId={7} comp={comp} wildShapeUses={null} />)
    expect(screen.queryByTestId('after-damage')).toBeNull()
    await userEvent.click(screen.getByText('character.turn.attack'))
    const reroll = await screen.findByTestId('after-damage')
    expect(reroll).toHaveAttribute('data-roll', 'weapon_damage')
    expect(reroll).toHaveAttribute('data-dice', '2/d6')
    await userEvent.click(reroll)
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('8 piercing'))
  })

  it('has no reroll on a miss or a damageless action', async () => {
    attack.mockResolvedValue({ ...result, damage_rolls: [], damage_total: 0, reroll_dice: undefined })
    renderWithProviders(<CompanionCard charId={7} comp={comp} wildShapeUses={null} />)
    await userEvent.click(screen.getByText('character.turn.attack'))
    await screen.findByRole('status')
    expect(screen.queryByTestId('after-damage')).toBeNull()
  })
})

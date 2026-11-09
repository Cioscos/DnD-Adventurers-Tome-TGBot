import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { ReactNode } from 'react'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import CompanionCard from '@/pages/extras/CompanionCard'
import type { Companion } from '@/types'

const { attack, hp } = vi.hoisted(() => ({ attack: vi.fn(), hp: vi.fn() }))

vi.mock('@/api/client', () => ({
  api: { companions: { attack, hp, remove: vi.fn(), deactivate: vi.fn(), activate: vi.fn() } },
  ApiError: class ApiError extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))
vi.mock('react-i18next', async (orig) => ({
  ...((await orig()) as Record<string, unknown>),
  useTranslation: () => ({ t: (k: string, o?: Record<string, unknown>) => (o?.dc !== undefined ? `${k}:${o.dc}:${o.m}` : k), i18n: { language: 'it' } }),
}))
vi.mock('@/hooks/useD20Roll', () => ({ useD20Roll: () => vi.fn().mockResolvedValue([12]) }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: vi.fn(), info: vi.fn(), success: vi.fn() }) }))
vi.mock('@/lib/mutationError', () => ({ notifyMutationError: vi.fn() }))
vi.mock('@/pages/hp/ConcentrationSaveDialog', () => ({ default: () => null }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/lib/rollOptions', async (orig) => ({
  ...((await orig()) as Record<string, unknown>),
  askRollOptions: vi.fn().mockResolvedValue({ options: [], option_inputs: {} }),
  refreshAfterOptions: vi.fn(),
}))
vi.mock('@/components/ui/RollButton', async () => {
  const React = await import('react')
  return { default: (p: { children?: ReactNode; onRoll: (m: string) => void; ariaLabel?: string }) =>
    React.createElement('button', { onClick: () => p.onRoll('normal'), 'aria-label': p.ariaLabel }, p.children) }
})

const imp = (over: Partial<Companion> = {}) => ({
  id: 3, character_id: 7, kind: 'familiar', name: 'Imp', srd_index: null, max_hp: 20, current_hp: 20, temp_hp: 0, armor_class: 13,
  notes: null, is_active: false, created_at: '', down: false, feature_key: null,
  statblock: { actions: [{ name: 'Morso', attack_bonus: 4, damage_dice: '1d4', damage_type: 'piercing' }] },
  save_dc: 14, fly_or_swim_m: 12, damage_type_options: ['necrotic', 'radiant'], can_resist: true, ...over,
}) as unknown as Companion

beforeEach(() => {
  attack.mockReset().mockResolvedValue({ to_hit_die: 12, to_hit_bonus: 4, to_hit_total: 16, is_critical: false, damage_total: 3, notes: [] })
  hp.mockReset().mockResolvedValue(imp())
})

describe('CompanionCard: famiglio con l\'Investitura del Padrone delle Catene', () => {
  it('shows the warlock DC and the speed, and attacks on the bonus action with the chosen damage type', async () => {
    renderWithProviders(<CompanionCard charId={7} comp={imp()} wildShapeUses={null} />)
    expect(screen.getByText('character.extras.chain_master.stats:14:12')).toBeTruthy()
    await userEvent.click(screen.getByRole('switch'))
    await userEvent.selectOptions(screen.getByRole('combobox'), 'radiant')
    await userEvent.click(screen.getByLabelText('character.turn.attack Morso'))
    await waitFor(() => expect(attack).toHaveBeenCalledWith(7, 3, 0, 'normal', [12], { options: [], option_inputs: {} }, undefined,
      { bonus: true, damage_type: 'radiant' }))
  })

  it('sends the reaction resistance with the damage', async () => {
    renderWithProviders(<CompanionCard charId={7} comp={imp()} wildShapeUses={null} />)
    await userEvent.type(screen.getByPlaceholderText('0'), '9')
    await userEvent.click(screen.getByText('character.extras.chain_master.resist'))
    await waitFor(() => expect(hp).toHaveBeenCalledWith(7, 3, 'damage', 9, true))
  })

  it('shows none of it for an ordinary familiar', () => {
    renderWithProviders(<CompanionCard charId={7} comp={imp({ damage_type_options: [], can_resist: false, save_dc: null })} wildShapeUses={null} />)
    expect(screen.queryByTestId('chain-master')).toBeNull()
    expect(screen.queryByText('character.extras.chain_master.resist')).toBeNull()
  })
})

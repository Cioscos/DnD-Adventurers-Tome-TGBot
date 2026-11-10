import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { ReactNode } from 'react'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import CompanionCard from '@/pages/extras/CompanionCard'
import CompanionForm from '@/pages/extras/CompanionForm'
import type { Companion } from '@/types'

const { attack, hitDice, toastError, toastInfo } = vi.hoisted(() => ({
  attack: vi.fn(), hitDice: vi.fn(), toastError: vi.fn(), toastInfo: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: { companions: { attack, hitDice, hp: vi.fn(), remove: vi.fn(), deactivate: vi.fn(), activate: vi.fn() } },
  ApiError: class ApiError extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))
vi.mock('react-i18next', async (orig) => ({
  ...((await orig()) as Record<string, unknown>),
  useTranslation: () => ({ t: (k: string, o?: Record<string, unknown>) => (o?.n !== undefined ? `${k}:${o.n}` : k), i18n: { language: 'it' } }),
}))
vi.mock('@/hooks/useD20Roll', () => ({ useD20Roll: () => vi.fn().mockResolvedValue([12]) }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: toastError, info: toastInfo, success: vi.fn() }) }))
vi.mock('@/lib/mutationError', async (orig) => ({ ...(await orig<typeof import('@/lib/mutationError')>()), notifyMutationError: vi.fn() }))
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
vi.mock('@/components/catalog/CatalogPicker', () => ({ default: () => null }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { children?: ReactNode }) => React.createElement('div', null, p.children) }
})

const beast = (over: Partial<Companion> = {}) => ({
  id: 3, character_id: 7, kind: 'companion', name: 'Pantera', srd_index: 'panther', max_hp: 13, current_hp: 5, temp_hp: 0,
  armor_class: 14, notes: null, is_active: false, created_at: '', down: false, feature_key: 'ranger.rangers_companion',
  statblock: { hit_dice: '3d8', hit_dice_spent: 1, actions: [{ name: 'Morso', attack_bonus: 4, damage_dice: '1d6+2' }] }, ...over,
}) as unknown as Companion

beforeEach(() => {
  attack.mockReset().mockResolvedValue({ to_hit_die: 12, to_hit_bonus: 6, to_hit_total: 18, is_critical: false, damage_total: 5, notes: [] })
  hitDice.mockReset().mockResolvedValue({ healed: 4, hit_dice_left: 1, rolls: [4], companion: beast() })
  toastError.mockReset()
  toastInfo.mockReset()
})

describe('CompanionCard: bestia del Signore delle Bestie', () => {
  it('spends a Hit Die and reports the healing and the dice left', async () => {
    renderWithProviders(<CompanionCard charId={7} comp={beast()} wildShapeUses={null} />)
    await userEvent.click(screen.getByText(/character.extras.beast.hit_dice \(2\/3\)/))
    await waitFor(() => expect(hitDice).toHaveBeenCalledWith(7, 3, 1))
    expect(toastInfo).toHaveBeenCalledWith('character.extras.beast.hit_dice_healed:4', { description: 'character.extras.beast.hit_dice_left:1' })
  })

  it('has no Hit Dice button at full HP, without dice left, or for another kind of companion', () => {
    renderWithProviders(<CompanionCard charId={7} comp={beast({ current_hp: 13 })} wildShapeUses={null} />)
    expect(screen.getByText(/character.extras.beast.hit_dice/)).toBeDisabled()
    renderWithProviders(<CompanionCard charId={7} comp={beast({ statblock: { hit_dice: '3d8', hit_dice_spent: 3, actions: [] } })} wildShapeUses={null} />)
    expect(screen.getAllByText(/character.extras.beast.hit_dice \(0\/3\)/)[0]).toBeDisabled()
    renderWithProviders(<CompanionCard charId={7} comp={beast({ feature_key: null })} wildShapeUses={null} />)
    expect(screen.getAllByText(/character.extras.beast.hit_dice/)).toHaveLength(2)
  })

  it('attacks as a reaction without an order, with the reaction flag', async () => {
    renderWithProviders(<CompanionCard charId={7} comp={beast()} wildShapeUses={null} />)
    await userEvent.click(screen.getByLabelText('character.extras.beast.reaction_attack Morso'))
    await waitFor(() => expect(attack).toHaveBeenCalled())
    expect(attack.mock.calls[0][6]).toBe(true)
    await userEvent.click(screen.getByLabelText('character.turn.attack Morso'))
    await waitFor(() => expect(attack).toHaveBeenCalledTimes(2))
    expect(attack.mock.calls[1][6]).toBeFalsy()
  })

  it('explains that the beast needs an order when the attack is refused', async () => {
    const { ApiError } = await import('@/api/client')
    attack.mockRejectedValue(new ApiError(409, { code: 'no_order' }))
    renderWithProviders(<CompanionCard charId={7} comp={beast()} wildShapeUses={null} />)
    await userEvent.click(screen.getByLabelText('character.turn.attack Morso'))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('character.extras.beast.no_order'))
  })
})

describe('CompanionForm: creare la bestia del ranger', () => {
  const open = (isBeastMaster: boolean, onSubmit = vi.fn()) => {
    renderWithProviders(<CompanionForm druidLevel={0} isMoon={false} edition="2014" isBeastMaster={isBeastMaster} onSubmit={onSubmit} onClose={() => {}} />)
    return onSubmit
  }

  it('sends the feature key only for a companion, when the Beast Master asks for it', async () => {
    const onSubmit = open(true)
    await userEvent.click(screen.getByText('character.extras.kinds.companion'))
    await userEvent.click(screen.getByRole('switch'))
    await userEvent.type(screen.getAllByRole('textbox')[0], 'Pantera')
    await userEvent.click(screen.getByText('common.add'))
    expect(onSubmit.mock.calls[0][0]).toMatchObject({ kind: 'companion', name: 'Pantera', feature_key: 'ranger.rangers_companion' })
  })

  it('offers nothing of the kind to anyone else', async () => {
    const onSubmit = open(false)
    await userEvent.click(screen.getByText('character.extras.kinds.companion'))
    expect(screen.queryByRole('switch')).toBeNull()
    await userEvent.type(screen.getAllByRole('textbox')[0], 'Gufo')
    await userEvent.click(screen.getByText('common.add'))
    expect(onSubmit.mock.calls[0][0].feature_key).toBeUndefined()
  })
})

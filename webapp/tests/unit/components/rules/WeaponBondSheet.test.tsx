import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import WeaponBondSheet from '@/components/rules/WeaponBondSheet'
import type { CharacterFull } from '@/types'

const { bond, breakBond, summon, toastError, toastInfo } = vi.hoisted(() => ({
  bond: vi.fn(), breakBond: vi.fn(), summon: vi.fn(), toastError: vi.fn(), toastInfo: vi.fn(),
}))
vi.mock('@/api/client', () => ({
  api: { items: { bond, breakBond, summon } },
  ApiError: class ApiError extends Error {
    constructor(public status = 0, public detail: unknown = null) {
      super(`API ${status}`)
    }
  },
}))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: toastError, info: toastInfo, success: vi.fn() }) }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string, o?: { name?: string }) => (o?.name ? `${k}:${o.name}` : k), i18n: { language: 'it' } }) }
})

const weapon = (id: number, name: string, extra: object = {}) => ({
  id, name, item_type: 'weapon', is_equipped: false, equipment_slot: null, item_metadata: {}, ...extra,
})
const charWith = (items: object[]) => ({ id: 7, items }) as unknown as CharacterFull

beforeEach(() => {
  bond.mockReset().mockResolvedValue({ id: 7, items: [] })
  breakBond.mockReset().mockResolvedValue({ id: 7, items: [] })
  summon.mockReset().mockResolvedValue({ id: 7, items: [] })
  toastError.mockReset()
  toastInfo.mockReset()
})

describe('WeaponBondSheet (Arma Vincolata)', () => {
  it('lists only the weapons and bonds one with the ritual', async () => {
    renderWithProviders(<WeaponBondSheet char={charWith([weapon(1, 'Spada'), { id: 2, name: 'Scudo', item_type: 'shield' }])} onClose={vi.fn()} />)
    expect(screen.getByText('Spada')).toBeInTheDocument()
    expect(screen.queryByText('Scudo')).not.toBeInTheDocument()
    await userEvent.click(screen.getByText('character.weapon_bond.bond'))
    await waitFor(() => expect(bond).toHaveBeenCalledWith(7, 1, undefined))
  })

  it('summons a bonded weapon and tells the player, and breaks a bond', async () => {
    renderWithProviders(<WeaponBondSheet char={charWith([weapon(1, 'Spada', { item_metadata: { bonded: true } })])} onClose={vi.fn()} />)
    await userEvent.click(screen.getByText('character.weapon_bond.summon'))
    await waitFor(() => expect(summon).toHaveBeenCalledWith(7, 1))
    expect(toastInfo).toHaveBeenCalledWith('character.weapon_bond.summoned')
    await userEvent.click(screen.getByText('character.weapon_bond.break'))
    await waitFor(() => expect(breakBond).toHaveBeenCalledWith(7, 1))
  })

  it('does not offer to summon a weapon that is already in hand', () => {
    renderWithProviders(<WeaponBondSheet char={charWith([
      weapon(1, 'Spada', { item_metadata: { bonded: true }, is_equipped: true, equipment_slot: 'main_hand' })])} onClose={vi.fn()} />)
    expect(screen.getByText('character.weapon_bond.in_hand').closest('button')).toBeDisabled()
  })

  it('with two bonds already, a third weapon asks which bond to break and sends it', async () => {
    renderWithProviders(<WeaponBondSheet char={charWith([
      weapon(1, 'Spada', { item_metadata: { bonded: true } }), weapon(2, 'Pugnale', { item_metadata: { bonded: true } }), weapon(3, 'Ascia'),
    ])} onClose={vi.fn()} />)
    await userEvent.click(screen.getByText('character.weapon_bond.bond'))
    expect(bond).not.toHaveBeenCalled()
    expect(screen.getByTestId('bond-replace')).toBeInTheDocument()
    await userEvent.click(screen.getByText('character.weapon_bond.break_for:Pugnale'))
    await waitFor(() => expect(bond).toHaveBeenCalledWith(7, 3, 2))
  })

  it('says why the server refused, with a text of its own', async () => {
    const { ApiError } = await import('@/api/client')
    summon.mockRejectedValueOnce(new ApiError(409, { code: 'no_free_hand' }))
    renderWithProviders(<WeaponBondSheet char={charWith([weapon(1, 'Spada', { item_metadata: { bonded: true } })])} onClose={vi.fn()} />)
    await userEvent.click(screen.getByText('character.weapon_bond.summon'))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('character.weapon_bond.errors.no_free_hand'))
  })

  it('has a text for an empty inventory', () => {
    renderWithProviders(<WeaponBondSheet char={charWith([])} onClose={vi.fn()} />)
    expect(screen.getByText('character.weapon_bond.empty')).toBeInTheDocument()
  })
})

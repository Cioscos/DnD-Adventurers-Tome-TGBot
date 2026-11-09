import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import PreserveLifeSheet from '@/components/rules/PreserveLifeSheet'
import type { CharacterFull } from '@/types'

const { preserveLifeInfo, preserveLife, toastError } = vi.hoisted(() => ({ preserveLifeInfo: vi.fn(), preserveLife: vi.fn(), toastError: vi.fn() }))
vi.mock('@/api/client', () => ({
  api: { characters: { preserveLifeInfo, preserveLife } },
  ApiError: class ApiError extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ info: vi.fn(), error: toastError, success: vi.fn() }) }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string, o?: Record<string, unknown>) => (o ? `${k}:${JSON.stringify(o)}` : k), i18n: { language: 'it' } }) }
})

const char = { id: 7 } as unknown as CharacterFull
const info = (targets: { id: number; name: string; cap: number; self: boolean }[], needs_confirm = true) => ({ pool: 25, uses_left: 1, targets, needs_confirm })

describe('PreserveLifeSheet', () => {
  it('sends the allocations only after the player confirms the targets are living', async () => {
    preserveLifeInfo.mockResolvedValue(info([{ id: 7, name: 'Tu', cap: 10, self: true }, { id: 9, name: 'Eroe', cap: 15, self: false }]))
    preserveLife.mockResolvedValue({ pool: 25, spent: 12, healed: [{ character_id: 9, name: 'Eroe', healed: 12 }] })
    renderWithProviders(<PreserveLifeSheet char={char} onClose={() => {}} />)
    await waitFor(() => expect(screen.getAllByPlaceholderText('0')).toHaveLength(2))  // chi usa e un alleato
    const inputs = screen.getAllByPlaceholderText('0')
    await userEvent.type(inputs[1], '12')
    const go = screen.getByText('character.turn.preserve_go').closest('button') as HTMLButtonElement
    expect(go).toBeDisabled()  // manca la conferma
    await userEvent.click(screen.getByRole('switch'))
    expect(go).toBeEnabled()
    await userEvent.click(go)
    await waitFor(() => expect(preserveLife).toHaveBeenCalledWith(7, { allocations: [{ character_id: 9, amount: 12 }], confirm_living: true }))
  })

  it('asks no confirmation when the server does not need one (2024 has no construct or undead exclusion)', async () => {
    preserveLifeInfo.mockResolvedValue(info([{ id: 7, name: 'Tu', cap: 10, self: true }], false))
    preserveLife.mockResolvedValue({ pool: 25, spent: 5, healed: [{ character_id: 7, name: 'Tu', healed: 5 }] })
    renderWithProviders(<PreserveLifeSheet char={char} onClose={() => {}} />)
    await waitFor(() => expect(screen.getAllByPlaceholderText('0')).toHaveLength(1))
    await userEvent.type(screen.getAllByPlaceholderText('0')[0], '5')
    expect(screen.queryByRole('switch')).not.toBeInTheDocument()
    const go = screen.getByText('character.turn.preserve_go').closest('button') as HTMLButtonElement
    expect(go).toBeEnabled()
    await userEvent.click(go)
    await waitFor(() => expect(preserveLife).toHaveBeenCalledWith(7, { allocations: [{ character_id: 7, amount: 5 }], confirm_living: false }))
  })

  it('refuses to send more than the pool or more than half of the maximum', async () => {
    preserveLifeInfo.mockResolvedValue(info([{ id: 7, name: 'Tu', cap: 10, self: true }, { id: 9, name: 'Eroe', cap: 15, self: false }]))
    renderWithProviders(<PreserveLifeSheet char={char} onClose={() => {}} />)
    await waitFor(() => expect(screen.getAllByPlaceholderText('0')).toHaveLength(2))
    const inputs = screen.getAllByPlaceholderText('0')
    await userEvent.type(inputs[1], '16')  // il server dice che restano 15
    await userEvent.click(screen.getByRole('switch'))
    expect(screen.getByText('character.turn.preserve_go').closest('button')).toBeDisabled()
    expect(screen.getByText(/preserve_cap/)).toBeInTheDocument()
  })

  it('says why the server refused, in plain words and never the technical message', async () => {
    const { ApiError } = await import('@/api/client')
    preserveLifeInfo.mockResolvedValue(info([{ id: 7, name: 'Tu', cap: 10, self: true }]))
    preserveLife.mockRejectedValue(new ApiError(422, { code: 'over_half' }))
    renderWithProviders(<PreserveLifeSheet char={char} onClose={() => {}} />)
    await waitFor(() => expect(screen.getAllByPlaceholderText('0')).toHaveLength(1))
    await userEvent.type(screen.getAllByPlaceholderText('0')[0], '5')
    await userEvent.click(screen.getByRole('switch'))
    await userEvent.click(screen.getByText('character.turn.preserve_go'))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('character.turn.preserve_errors.over_half'))
  })

  it('does not show the hit points of anyone', async () => {
    preserveLifeInfo.mockResolvedValue(info([{ id: 9, name: 'Eroe', cap: 15, self: false }]))
    renderWithProviders(<PreserveLifeSheet char={char} onClose={() => {}} />)
    await waitFor(() => expect(screen.getByText(/Eroe/)).toBeInTheDocument())
    expect(screen.queryByText(/\d+\/\d+/)).not.toBeInTheDocument()
  })
})

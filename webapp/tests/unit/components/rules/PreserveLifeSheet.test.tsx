import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import PreserveLifeSheet from '@/components/rules/PreserveLifeSheet'
import type { CharacterFull } from '@/types'

const { sessionAllies, preserveLife } = vi.hoisted(() => ({ sessionAllies: vi.fn(), preserveLife: vi.fn() }))
vi.mock('@/api/client', () => ({ api: { characters: { sessionAllies, preserveLife } } }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ info: vi.fn(), error: vi.fn(), success: vi.fn() }) }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string, o?: Record<string, unknown>) => (o ? `${k}:${JSON.stringify(o)}` : k), i18n: { language: 'it' } }) }
})

const char = { id: 7, current_hit_points: 10, hit_points: 40 } as unknown as CharacterFull

describe('PreserveLifeSheet', () => {
  it('sends the allocations only after the player confirms the targets are living', async () => {
    sessionAllies.mockResolvedValue([{ id: 9, name: 'Eroe', hp: 5, hp_max: 40, die: null }])
    preserveLife.mockResolvedValue({ pool: 25, spent: 12, healed: [{ character_id: 9, name: 'Eroe', healed: 12, current_hit_points: 17 }] })
    renderWithProviders(<PreserveLifeSheet char={char} pool={25} onClose={() => {}} />)
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

  it('refuses to send more than the pool or more than half of the maximum', async () => {
    sessionAllies.mockResolvedValue([{ id: 9, name: 'Eroe', hp: 5, hp_max: 40 }])
    renderWithProviders(<PreserveLifeSheet char={char} pool={25} onClose={() => {}} />)
    await waitFor(() => expect(screen.getAllByPlaceholderText('0')).toHaveLength(2))
    const inputs = screen.getAllByPlaceholderText('0')
    await userEvent.type(inputs[1], '16')  // 5 + 16 = 21 oltre la metà di 40
    await userEvent.click(screen.getByRole('switch'))
    expect(screen.getByText('character.turn.preserve_go').closest('button')).toBeDisabled()
    expect(screen.getByText(/preserve_cap/)).toBeInTheDocument()
  })
})

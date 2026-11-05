import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import AllyTargetSheet from '@/components/rules/AllyTargetSheet'

vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return {
    ...actual,
    useTranslation: () => ({ t: (k: string, o?: { die?: number }) => (o?.die ? `${k}:${o.die}` : k), i18n: { language: 'it' } }),
  }
})

const allies = [{ id: 31, name: 'Brun', die: null }, { id: 32, name: 'Lia', die: 10 }]

describe('AllyTargetSheet', () => {
  it('picks an ally without a die straight away', async () => {
    const onPick = vi.fn()
    renderWithProviders(<AllyTargetSheet allies={allies} onPick={onPick} onClose={() => {}} />)
    await userEvent.click(screen.getByText('Brun'))
    expect(onPick).toHaveBeenCalledWith(31)
  })

  it('has an exit for a creature that has no sheet at the table, which uses it without a target', async () => {
    const onPick = vi.fn()
    renderWithProviders(<AllyTargetSheet allies={allies} onPick={onPick} onClose={() => {}} />)
    await userEvent.click(screen.getByText('character.turn.ally_other'))
    expect(onPick).toHaveBeenCalledWith(null)
  })

  it('warns before replacing a die the ally already holds, and spends only on confirm', async () => {
    const onPick = vi.fn()
    renderWithProviders(<AllyTargetSheet allies={allies} onPick={onPick} onClose={() => {}} />)
    await userEvent.click(screen.getByText('Lia'))
    expect(onPick).not.toHaveBeenCalled()
    expect(screen.getByText('character.turn.ally_has_die:10')).toBeInTheDocument()
    await userEvent.click(screen.getByText('character.turn.ally_replace'))
    expect(onPick).toHaveBeenCalledWith(32)
  })

  it('goes back from the warning without spending', async () => {
    const onPick = vi.fn()
    renderWithProviders(<AllyTargetSheet allies={allies} onPick={onPick} onClose={() => {}} />)
    await userEvent.click(screen.getByText('Lia'))
    await userEvent.click(screen.getByText('character.turn.ally_back'))
    expect(onPick).not.toHaveBeenCalled()
    expect(screen.getByText('Brun')).toBeInTheDocument()
  })
})

import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import AllyTargetSheet from '@/components/rules/AllyTargetSheet'

vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; title?: string; children?: unknown }) => (p.open ? React.createElement('div', null, React.createElement('h2', null, p.title), p.children) : null) }
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
    renderWithProviders(<AllyTargetSheet title="Ispirazione Bardica" die allies={allies} onPick={onPick} onClose={() => {}} />)
    await userEvent.click(screen.getByText('Brun'))
    expect(onPick).toHaveBeenCalledWith(31)
  })

  it('has an exit for a creature that has no sheet at the table, which uses it without a target', async () => {
    const onPick = vi.fn()
    renderWithProviders(<AllyTargetSheet title="Ispirazione Bardica" die allies={allies} onPick={onPick} onClose={() => {}} />)
    await userEvent.click(screen.getByText('character.turn.ally_other'))
    expect(onPick).toHaveBeenCalledWith(null)
  })

  it('warns before replacing a die the ally already holds, and spends only on confirm', async () => {
    const onPick = vi.fn()
    renderWithProviders(<AllyTargetSheet title="Ispirazione Bardica" die allies={allies} onPick={onPick} onClose={() => {}} />)
    await userEvent.click(screen.getByText('Lia'))
    expect(onPick).not.toHaveBeenCalled()
    expect(screen.getByText('character.turn.ally_has_die:10')).toBeInTheDocument()
    await userEvent.click(screen.getByText('character.turn.ally_replace'))
    expect(onPick).toHaveBeenCalledWith(32)
  })

  it('goes back from the warning without spending', async () => {
    const onPick = vi.fn()
    renderWithProviders(<AllyTargetSheet title="Ispirazione Bardica" die allies={allies} onPick={onPick} onClose={() => {}} />)
    await userEvent.click(screen.getByText('Lia'))
    await userEvent.click(screen.getByText('character.turn.ally_back'))
    expect(onPick).not.toHaveBeenCalled()
    expect(screen.getByText('Brun')).toBeInTheDocument()
  })

  it('is titled by the feature that opened it and does not ask for a die when it gives none', () => {
    renderWithProviders(<AllyTargetSheet title="Benedizione dell'Ingannatore" allies={allies} onPick={() => {}} onClose={() => {}} />)
    expect(screen.getByRole('heading')).toHaveTextContent("Benedizione dell'Ingannatore")
    expect(screen.getByText('character.turn.ally_pick_effect')).toBeInTheDocument()
    expect(screen.queryByText('character.turn.ally_pick')).toBeNull()  // «A chi dai il dado?» è solo del dado di Ispirazione
    expect(screen.queryByText('d10')).toBeNull()
  })

  it('does not warn about replacing when the feature gives no die', async () => {
    const onPick = vi.fn()
    renderWithProviders(<AllyTargetSheet title="Benedizione dell'Ingannatore" allies={allies} onPick={onPick} onClose={() => {}} />)
    await userEvent.click(screen.getByText('Lia'))
    expect(onPick).toHaveBeenCalledWith(32)
  })
})

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

  it('with several recipients allowed it toggles up to the maximum and confirms them in one go', async () => {
    const onPickMany = vi.fn()
    const three = [...allies, { id: 33, name: 'Tor', die: null }]
    renderWithProviders(<AllyTargetSheet title="Mantello" allies={three} max={2} onPickMany={onPickMany} onPick={() => {}} onClose={() => {}} />)
    await userEvent.click(screen.getByText('Brun'))
    await userEvent.click(screen.getByText('Lia'))
    await userEvent.click(screen.getByText('Tor'))  // oltre il massimo: ignorato
    await userEvent.click(screen.getByText('character.turn.ally_confirm'))
    expect(onPickMany).toHaveBeenCalledWith([31, 32])
  })

  describe('removal of conditions (Task 48)', () => {
    const removal = (over = {}) => ({
      conditions: [{ key: 'blinded', label: { it: 'Accecato', en: 'Blinded' } }, { key: 'deafened', label: { it: 'Assordato', en: 'Deafened' } }],
      untracked: [{ key: 'disease', label: { it: 'malattia', en: 'disease' } }],
      count: 1, maxTargets: 1, onConfirm: vi.fn(), ...over,
    })

    it('picks one condition and one target, then confirms; confirm stays off until both are chosen', async () => {
      const r = removal()
      renderWithProviders(<AllyTargetSheet title="Ristorare" allies={allies} removal={r} onPick={() => {}} onClose={() => {}} />)
      const confirm = screen.getByText('character.turn.removal_confirm').closest('button')!
      expect(confirm).toBeDisabled()
      await userEvent.click(screen.getByText('Accecato'))
      await userEvent.click(screen.getByText('Assordato'))  // count 1: la seconda sostituisce la prima
      await userEvent.click(screen.getByText('Brun'))
      expect(confirm).toBeEnabled()
      await userEvent.click(confirm)
      expect(r.onConfirm).toHaveBeenCalledWith({ targets: [31], conditions: ['deafened'] })
    })

    it('offers the untracked entry as a choice, and the creature outside the evening', async () => {
      const r = removal()
      renderWithProviders(<AllyTargetSheet title="Ristorare" allies={allies} removal={r} onPick={() => {}} onClose={() => {}} />)
      await userEvent.click(screen.getByText('malattia'))
      await userEvent.click(screen.getByText('character.turn.ally_other'))
      await userEvent.click(screen.getByText('character.turn.removal_confirm'))
      expect(r.onConfirm).toHaveBeenCalledWith({ targets: ['other'], conditions: ['disease'] })
    })

    it('a spell that removes everything asks only for the targets, up to the maximum', async () => {
      const r = removal({ count: null, maxTargets: 2 })
      renderWithProviders(<AllyTargetSheet title="Guarigione di Massa" allies={allies} removal={r} onPick={() => {}} onClose={() => {}} />)
      expect(screen.queryByText('Accecato')).toBeNull()
      await userEvent.click(screen.getByText('character.turn.removal_self'))
      await userEvent.click(screen.getByText('Brun'))
      await userEvent.click(screen.getByText('Lia'))  // oltre il massimo: ignorato
      await userEvent.click(screen.getByText('character.turn.removal_confirm'))
      expect(r.onConfirm).toHaveBeenCalledWith({ targets: ['self', 31] })
    })
  })
})

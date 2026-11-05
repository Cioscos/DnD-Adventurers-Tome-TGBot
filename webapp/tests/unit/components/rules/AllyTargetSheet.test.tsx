import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import AllyTargetSheet from '@/components/rules/AllyTargetSheet'

vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { title?: string; children?: unknown }) => React.createElement('div', null, React.createElement('h2', null, p.title), p.children) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

describe('AllyTargetSheet', () => {
  it('is titled by the feature that opened it, not by the bardic one', () => {
    renderWithProviders(<AllyTargetSheet title="Benedizione dell'Ingannatore" allies={[{ id: 9, name: 'Eroe' }]} onPick={() => {}} onClose={() => {}} />)
    expect(screen.getByRole('heading')).toHaveTextContent("Benedizione dell'Ingannatore")
    expect(screen.getByText('character.turn.ally_pick_effect')).toBeInTheDocument()
    expect(screen.queryByText('character.turn.ally_pick')).toBeNull()  // «A chi dai il dado?» è solo del dado di Ispirazione
  })

  it('asks "who gets the die" only for the bardic die, and warns before replacing one', async () => {
    const onPick = vi.fn()
    renderWithProviders(<AllyTargetSheet title="Ispirazione Bardica" die allies={[{ id: 9, name: 'Eroe', die: 8 }]} onPick={onPick} onClose={() => {}} />)
    expect(screen.getByText('character.turn.ally_pick')).toBeInTheDocument()
    await userEvent.click(screen.getByText('Eroe'))
    expect(screen.getByText('character.turn.ally_has_die')).toBeInTheDocument()
    await userEvent.click(screen.getByText('character.turn.ally_replace'))
    expect(onPick).toHaveBeenCalledWith(9)
  })
})

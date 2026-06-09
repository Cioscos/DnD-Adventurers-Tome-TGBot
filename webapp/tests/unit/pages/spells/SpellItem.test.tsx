import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SpellItem from '@/pages/spells/SpellItem'
import type { Spell } from '@/types'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

const spell = (over: Partial<Spell> = {}): Spell =>
  ({ id: 1, name: 'Dardo Incantato', level: 1, description: 'Tre dardi', is_concentration: false, is_ritual: false, is_pinned: false, ...over } as Spell)

const base = {
  onToggle: () => {}, onUse: () => {}, onConcentrationToggle: () => {}, onEdit: () => {}, onRemove: () => {},
  concentratingSpellId: null, usePending: false,
}

describe('SpellItem', () => {
  it('renders the spell name and toggles on header click', async () => {
    const onToggle = vi.fn()
    render(<SpellItem spell={spell()} isExpanded={false} {...base} onToggle={onToggle} />)
    expect(screen.getByText('Dardo Incantato')).toBeInTheDocument()
    await userEvent.click(screen.getByText('Dardo Incantato'))
    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  it('when expanded shows the description and a use action', async () => {
    const onUse = vi.fn()
    render(<SpellItem spell={spell()} isExpanded {...base} onUse={onUse} />)
    expect(screen.getByText('Tre dardi')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /character.spells.use/ }))
    expect(onUse).toHaveBeenCalledTimes(1)
  })

  it('shows the concentration toggle only for concentration spells', async () => {
    const onConcentrationToggle = vi.fn()
    const { rerender } = render(<SpellItem spell={spell()} isExpanded {...base} onConcentrationToggle={onConcentrationToggle} />)
    expect(screen.queryByRole('button', { name: 'character.spells.concentration_button_title' })).not.toBeInTheDocument()
    rerender(<SpellItem spell={spell({ is_concentration: true })} isExpanded {...base} onConcentrationToggle={onConcentrationToggle} />)
    await userEvent.click(screen.getByRole('button', { name: 'character.spells.concentration_button_title' }))
    expect(onConcentrationToggle).toHaveBeenCalledTimes(1)
  })

  it('edit and remove are reachable through the actions menu', async () => {
    const onEdit = vi.fn()
    const onRemove = vi.fn()
    render(<SpellItem spell={spell()} isExpanded {...base} onEdit={onEdit} onRemove={onRemove} />)
    await userEvent.click(screen.getByRole('button', { name: 'character.spells.more_actions' }))
    await userEvent.click(screen.getByRole('menuitem', { name: /character.spells.edit/ }))
    expect(onEdit).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('button', { name: 'character.spells.more_actions' }))
    await userEvent.click(screen.getByRole('menuitem', { name: /character.spells.forget/ }))
    expect(onRemove).toHaveBeenCalledTimes(1)
  })
})

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

  it('shows C/R badges as pills and the shared expand chevron', () => {
    const { container } = render(
      <SpellItem spell={spell({ is_concentration: true, is_ritual: true })} isExpanded={false} {...base} />,
    )
    expect(screen.getByTitle('character.spells.badge_concentration')).toBeInTheDocument()
    expect(screen.getByTitle('character.spells.badge_ritual')).toBeInTheDocument()
    expect(screen.getByText('C')).toBeInTheDocument()
    expect(screen.getByText('R')).toBeInTheDocument()
    // wrapper aria-hidden con svg = ExpandChevron (le icone lucide hanno aria-hidden sull'svg, non su uno span)
    expect(container.querySelector('span[aria-hidden] svg')).not.toBeNull()
  })

  it('uses the parchment variant when castable and the flat variant when unprepared', () => {
    const preparing = { showPreparedToggle: true, onPreparedToggle: () => {}, preparedPending: false }
    const { container, rerender } = render(
      <SpellItem spell={spell({ is_prepared: false })} isExpanded={false} {...base} {...preparing} />,
    )
    expect((container.firstChild as HTMLElement).className).toContain('bg-dnd-surface')
    rerender(
      <SpellItem spell={spell({ is_prepared: true })} isExpanded={false} {...base} {...preparing} />,
    )
    expect((container.firstChild as HTMLElement).className).toContain('bg-gradient-parchment')
  })
})

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AbilityModifiersEditor from '@/pages/inventory/AbilityModifiersEditor'
import type { AbilityModifier } from '@/types'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

describe('AbilityModifiersEditor', () => {
  it('shows the empty hint when there are no modifiers', () => {
    render(<AbilityModifiersEditor modifiers={[]} onChange={() => {}} />)
    expect(screen.getByText('character.inventory.item.modifiers.empty')).toBeInTheDocument()
  })

  it('add appends a default STR / relative / 0 modifier', async () => {
    const onChange = vi.fn()
    render(<AbilityModifiersEditor modifiers={[]} onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: 'character.inventory.item.modifiers.add' }))
    expect(onChange).toHaveBeenCalledWith([{ ability: 'strength', kind: 'relative', value: 0 }])
  })

  it('editing the value emits an updated modifier', async () => {
    const onChange = vi.fn()
    const mods: AbilityModifier[] = [{ ability: 'strength', kind: 'relative', value: 0 }]
    render(<AbilityModifiersEditor modifiers={mods} onChange={onChange} />)
    const input = screen.getByLabelText('character.inventory.item.modifiers.value')
    fireEvent.change(input, { target: { value: '2' } })
    expect(onChange).toHaveBeenLastCalledWith([{ ability: 'strength', kind: 'relative', value: 2 }])
  })

  it('changing the ability via its chip emits an updated modifier', async () => {
    const onChange = vi.fn()
    const mods: AbilityModifier[] = [{ ability: 'strength', kind: 'relative', value: 1 }]
    render(<AbilityModifiersEditor modifiers={mods} onChange={onChange} />)
    expect(screen.getByRole('radio', { name: 'character.ability.strength_short' }))
      .toHaveAttribute('aria-checked', 'true')
    await userEvent.click(screen.getByRole('radio', { name: 'character.ability.dexterity_short' }))
    expect(onChange).toHaveBeenCalledWith([{ ability: 'dexterity', kind: 'relative', value: 1 }])
  })

  it('changing the kind via its chip emits an updated modifier', async () => {
    const onChange = vi.fn()
    const mods: AbilityModifier[] = [{ ability: 'strength', kind: 'relative', value: 1 }]
    render(<AbilityModifiersEditor modifiers={mods} onChange={onChange} />)
    await userEvent.click(screen.getByRole('radio', { name: 'character.inventory.item.modifiers.kind.absolute' }))
    expect(onChange).toHaveBeenCalledWith([{ ability: 'strength', kind: 'absolute', value: 1 }])
  })

  it('remove drops the modifier at its index', async () => {
    const onChange = vi.fn()
    const mods: AbilityModifier[] = [{ ability: 'strength', kind: 'relative', value: 1 }]
    render(<AbilityModifiersEditor modifiers={mods} onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: 'character.inventory.item.modifiers.remove' }))
    expect(onChange).toHaveBeenCalledWith([])
  })
})

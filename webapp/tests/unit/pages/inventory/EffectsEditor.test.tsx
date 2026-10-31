import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { LazyMotion, domMax } from 'framer-motion'
import userEvent from '@testing-library/user-event'
import EffectsEditor from '@/pages/inventory/EffectsEditor'
import type { ItemEffect } from '@/pages/inventory/itemMetadata'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

describe('EffectsEditor', () => {
  it('shows the empty hint when there are no effects', () => {
    render(<EffectsEditor effects={[]} onChange={() => {}} />)
    expect(screen.getByText('character.inventory.effects.empty')).toBeInTheDocument()
  })

  it('add appends a default heal effect (2d4+2)', async () => {
    const onChange = vi.fn()
    render(<EffectsEditor effects={[]} onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: 'character.inventory.effects.add' }))
    expect(onChange).toHaveBeenCalledWith([{ kind: 'heal', amount: '2d4+2' }])
  })

  it('editing a heal amount emits the updated effect', async () => {
    const onChange = vi.fn()
    const effects: ItemEffect[] = [{ kind: 'heal', amount: '1d4' }]
    render(<EffectsEditor effects={effects} onChange={onChange} />)
    const input = screen.getByLabelText('character.inventory.effects.amount_label')
    fireEvent.change(input, { target: { value: '3d6' } })
    expect(onChange).toHaveBeenLastCalledWith([{ kind: 'heal', amount: '3d6' }])
  })

  it('switching kind to a condition effect resets it to a default condition payload', async () => {
    const onChange = vi.fn()
    const effects: ItemEffect[] = [{ kind: 'heal', amount: '2d4+2' }]
    render(<EffectsEditor effects={effects} onChange={onChange} />)
    await userEvent.click(screen.getByRole('radio', { name: 'character.inventory.effects.kinds.add_condition' }))
    expect(onChange).toHaveBeenCalledWith([{ kind: 'add_condition', condition: 'poisoned' }])
  })

  it('picking a condition from the SelectSheet emits the updated effect', async () => {
    const onChange = vi.fn()
    const effects: ItemEffect[] = [{ kind: 'add_condition', condition: 'poisoned' }]
    // come in main.tsx: senza LazyMotion i feature di animazione non girano e il backdrop
    // dello Sheet (initial pointer-events:none) non diventa mai cliccabile
    render(<LazyMotion features={domMax}><EffectsEditor effects={effects} onChange={onChange} /></LazyMotion>)
    // trigger shows the current condition, the sheet lists them all
    await userEvent.click(screen.getByRole('button', { name: /character\.conditions\.poisoned/ }))
    const option = await screen.findByRole('radio', { name: 'character.conditions.blinded' })
    await waitFor(() => expect(option.closest('[class*="fixed"]')).toHaveStyle({ pointerEvents: 'auto' }))
    await userEvent.click(option)
    expect(onChange).toHaveBeenCalledWith([{ kind: 'add_condition', condition: 'blinded' }])
  })

  it('remove drops the effect', async () => {
    const onChange = vi.fn()
    const effects: ItemEffect[] = [{ kind: 'heal', amount: '2d4+2' }]
    render(<EffectsEditor effects={effects} onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: 'common.remove' }))
    expect(onChange).toHaveBeenCalledWith([])
  })
})

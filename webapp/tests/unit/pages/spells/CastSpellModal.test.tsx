import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CastSpellModal from '@/pages/spells/CastSpellModal'
import type { Spell, SpellSlot } from '@/types'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void; disabled?: boolean; loading?: boolean; children?: unknown }) => React.createElement('button', { onClick: p.onClick, disabled: p.disabled || p.loading }, p.children) }
})

const spell = { id: 1, name: 'Palla di Fuoco', level: 3 } as Spell
const noop = () => {}

describe('CastSpellModal', () => {
  it('offers slot buttons and casts at the chosen level', async () => {
    const onCast = vi.fn()
    const slots = [{ id: 10, level: 3, available: 2, used: 1, total: 3 }] as SpellSlot[]
    render(<CastSpellModal spell={spell} availableSlots={slots} onCast={onCast} onCreateSlot={noop} onCancel={noop} isPending={false} isCreatingSlot={false} />)
    await userEvent.click(screen.getByText('character.slots.available_count'))
    expect(onCast).toHaveBeenCalledWith(slots[0])
  })

  it('tells the two pools of the same level apart and casts from the chosen one', async () => {
    const onCast = vi.fn()
    const slots = [
      { id: 10, level: 3, available: 2, used: 0, total: 2, is_pact: false },
      { id: 11, level: 3, available: 1, used: 1, total: 2, is_pact: true },
    ] as SpellSlot[]
    render(<CastSpellModal spell={spell} availableSlots={slots} onCast={onCast} onCreateSlot={noop} onCancel={noop} isPending={false} isCreatingSlot={false} />)
    await userEvent.click(screen.getByRole('button', { name: /character.slots.pact_badge/ }))
    expect(onCast).toHaveBeenCalledWith(slots[1])
    expect(screen.getAllByText(/character.slots.pact_badge/)).toHaveLength(1)
  })

  it('with no slots, prompts to create one at the spell level', async () => {
    const onCreateSlot = vi.fn()
    render(<CastSpellModal spell={spell} availableSlots={[]} onCast={noop} onCreateSlot={onCreateSlot} onCancel={noop} isPending={false} isCreatingSlot={false} />)
    expect(screen.getByText('character.spells.no_slots')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'character.spells.go_create_slot' }))
    expect(onCreateSlot).toHaveBeenCalledWith(3)
  })

  it('cancels', async () => {
    const onCancel = vi.fn()
    render(<CastSpellModal spell={spell} availableSlots={[]} onCast={noop} onCreateSlot={noop} onCancel={onCancel} isPending={false} isCreatingSlot={false} />)
    await userEvent.click(screen.getByRole('button', { name: 'common.cancel' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  describe('ki cast (Shadow Arts, Four Elements disciplines)', () => {
    const common = { spell, availableSlots: [] as SpellSlot[], onCast: vi.fn(), onCreateSlot: noop, onCancel: noop, isPending: false, isCreatingSlot: false }
    const ki = { cost: 2, max_extra: 0, ki_left: 5, feature_key: 'monk.discipline_sweeping_cinder_strike' }

    it('casts with the ki and, with no slots at all, hides the invitation to create one', async () => {
      const onCastKi = vi.fn()
      render(<CastSpellModal {...common} kiCast={ki} onCastKi={onCastKi} />)
      expect(screen.queryByText('character.spells.no_slots')).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'character.spells.go_create_slot' })).not.toBeInTheDocument()
      await userEvent.click(screen.getByRole('button', { name: 'character.spells.cast_ki' }))
      expect(onCastKi).toHaveBeenCalledWith(0)
    })

    it('lets the player add extra ki up to the allowed maximum and sends it', async () => {
      const onCastKi = vi.fn()
      render(<CastSpellModal {...common} kiCast={{ ...ki, max_extra: 1 }} onCastKi={onCastKi} />)
      const more = screen.getByLabelText('character.turn.amount_more')
      await userEvent.click(more)
      await userEvent.click(more)
      expect(screen.getByTestId('use-amount')).toHaveTextContent('1')  // mai oltre il tetto
      await userEvent.click(screen.getByRole('button', { name: 'character.spells.cast_ki' }))
      expect(onCastKi).toHaveBeenCalledWith(1)
    })

    it('shows no extra selector when the spell cannot be raised, and turns the cast off without enough ki', () => {
      const { rerender } = render(<CastSpellModal {...common} kiCast={ki} onCastKi={vi.fn()} />)
      expect(screen.queryByTestId('use-amount')).not.toBeInTheDocument()
      rerender(<CastSpellModal {...common} kiCast={{ ...ki, ki_left: 1 }} onCastKi={vi.fn()} />)
      expect(screen.getByRole('button', { name: 'character.spells.cast_ki' })).toBeDisabled()
      expect(screen.getByText('character.spells.cast_ki_none')).toBeInTheDocument()
    })

    it('keeps the slots when the character has some, next to the ki cast', async () => {
      const slots = [{ id: 10, level: 3, available: 2, used: 0, total: 2 }] as SpellSlot[]
      render(<CastSpellModal {...common} availableSlots={slots} kiCast={ki} onCastKi={vi.fn()} />)
      expect(screen.getByText('character.slots.available_count')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'character.spells.cast_ki' })).toBeInTheDocument()
    })
  })

  it('offers the free cast only when an active effect allows it, even with no slots left', async () => {
    const onCastFree = vi.fn()
    const common = { spell, availableSlots: [] as SpellSlot[], onCast: vi.fn(), onCreateSlot: noop, onCancel: noop, isPending: false, isCreatingSlot: false }
    const { rerender } = render(<CastSpellModal {...common} />)
    expect(screen.queryByText('character.spells.cast_free')).not.toBeInTheDocument()
    rerender(<CastSpellModal {...common} canFreeCast onCastFree={onCastFree} />)
    await userEvent.click(screen.getByText('character.spells.cast_free'))
    expect(onCastFree).toHaveBeenCalledTimes(1)
  })
})

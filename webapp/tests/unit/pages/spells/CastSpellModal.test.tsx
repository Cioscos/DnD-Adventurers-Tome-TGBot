import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CastSpellModal from '@/pages/spells/CastSpellModal'
import type { Spell, SpellSlot } from '@/types'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
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
    const slots = [{ id: 10, level: 3, available: 2, total: 3 }] as SpellSlot[]
    render(<CastSpellModal spell={spell} availableSlots={slots} onCast={onCast} onCreateSlot={noop} onCancel={noop} isPending={false} isCreatingSlot={false} />)
    await userEvent.click(screen.getByText(/2\/3/))
    expect(onCast).toHaveBeenCalledWith(3)
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
})

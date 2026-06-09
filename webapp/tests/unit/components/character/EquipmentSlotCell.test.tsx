import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import EquipmentSlotCell from '@/components/character/EquipmentSlotCell'
import type { Item } from '@/types'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
// useReducedMotion lives in framer-motion here → return true to skip the halo timer.
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'drag', 'layout', 'layoutId'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return {
    m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }),
    useReducedMotion: () => true,
  }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/lib/equipmentSlots', async () => {
  const React = await import('react')
  return {
    SLOT_PLACEHOLDER_ICON: new Proxy({}, { get: () => () => React.createElement('span', { 'data-testid': 'placeholder' }) }),
    equippedItemIcon: () => null, // → cell falls back to the item's initial letter
  }
})

const helmet = { id: 1, name: 'Helmet', item_type: 'armor', is_equipped: true, equipment_slot: 'head', weight: 2, quantity: 1 } as Item

describe('EquipmentSlotCell', () => {
  it('renders the placeholder icon and an "empty" label when no item is equipped', async () => {
    const onTap = vi.fn()
    render(<EquipmentSlotCell slot="head" equipped={null} onTap={onTap} />)
    expect(screen.getByTestId('placeholder')).toBeInTheDocument()
    const btn = screen.getByRole('button')
    expect(btn).toHaveAttribute('aria-label', expect.stringContaining('character.equipment.picker.empty'))
    await userEvent.click(btn)
    expect(onTap).toHaveBeenCalledWith(null)
  })

  it('renders the equipped item initial and a labelled cell, and taps with the item', async () => {
    const onTap = vi.fn()
    render(<EquipmentSlotCell slot="head" equipped={helmet} onTap={onTap} />)
    expect(screen.getByText('H')).toBeInTheDocument() // initial of "Helmet"
    expect(screen.getByRole('button')).toHaveAttribute('aria-label', 'character.equipment.slots.head: Helmet')
    await userEvent.click(screen.getByRole('button'))
    expect(onTap).toHaveBeenCalledWith(helmet)
  })
})

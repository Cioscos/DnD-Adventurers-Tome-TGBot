import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import SlotActionSheet from '@/components/character/SlotActionSheet'
import type { Item } from '@/types'

const { updateSpy } = vi.hoisted(() => ({ updateSpy: vi.fn() }))

vi.mock('@/api/client', () => ({ api: { items: { update: updateSpy } } }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'drag', 'layout'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return {
    m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }),
    AnimatePresence: (p: { children?: unknown }) => React.createElement(React.Fragment, null, p.children),
  }
})
vi.mock('@/store/overlayStore', () => ({ useRegisterOverlay: () => {} }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))

const item = { id: 7, name: 'Longsword', item_type: 'weapon', is_equipped: true, equipment_slot: 'main_hand', weight: 3, quantity: 1 } as Item

afterEach(() => updateSpy.mockReset())

function setup(extra: { onClose?: () => void; onReplace?: () => void; onDetails?: (i: Item) => void } = {}) {
  return renderWithProviders(
    <SlotActionSheet
      charId={42}
      slot="main_hand"
      item={item}
      onClose={extra.onClose ?? (() => {})}
      onReplace={extra.onReplace ?? (() => {})}
      onDetails={extra.onDetails ?? (() => {})}
    />,
  )
}

describe('SlotActionSheet', () => {
  it('renders the item header and the three actions', () => {
    setup()
    expect(screen.getByText('Longsword')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'character.equipment.actions.details' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'character.equipment.actions.replace' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'character.equipment.actions.unequip' })).toBeInTheDocument()
  })

  it('details and replace fire their callbacks', async () => {
    const onDetails = vi.fn()
    const onReplace = vi.fn()
    setup({ onDetails, onReplace })
    await userEvent.click(screen.getByRole('button', { name: 'character.equipment.actions.details' }))
    expect(onDetails).toHaveBeenCalledWith(item)
    await userEvent.click(screen.getByRole('button', { name: 'character.equipment.actions.replace' }))
    expect(onReplace).toHaveBeenCalledTimes(1)
  })

  it('unequip PATCHes the item to is_equipped:false / equipment_slot:null, then closes (contract)', async () => {
    const onClose = vi.fn()
    updateSpy.mockResolvedValue({ id: 42 })
    setup({ onClose })
    await userEvent.click(screen.getByRole('button', { name: 'character.equipment.actions.unequip' }))
    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith(42, 7, { is_equipped: false, equipment_slot: null }))
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
  })

  it('tapping the backdrop closes the sheet', async () => {
    const onClose = vi.fn()
    setup({ onClose })
    const backdrop = document.querySelector('.fixed.inset-0') as HTMLElement
    fireEvent.click(backdrop)
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})

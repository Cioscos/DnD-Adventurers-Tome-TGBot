import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import EquipItemPicker from '@/components/character/EquipItemPicker'
import type { Item } from '@/types'

const { updateSpy, handsConflictSpy, navigateSpy } = vi.hoisted(() => ({
  updateSpy: vi.fn(),
  handsConflictSpy: vi.fn(),
  navigateSpy: vi.fn(),
}))

vi.mock('@/api/client', () => ({ api: { items: { update: updateSpy } } }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useNavigate: () => navigateSpy }
})
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
    AnimatePresence: (p: { children?: unknown }) => React.createElement(React.Fragment, null, p.children),
  }
})
vi.mock('@/store/overlayStore', () => ({ useRegisterOverlay: () => {} }))
vi.mock('@/store/unitSettings', () => ({
  useUnitSettings: (sel: (s: { system: string }) => unknown) => sel({ system: 'imperial' }),
  formatWeight: (v: number) => `${v} lb`,
}))
vi.mock('@/lib/equipmentSlots', () => ({
  ITEM_TYPE_TO_SLOTS: { weapon: ['main_hand', 'off_hand'], shield: ['off_hand'], armor: ['body'] },
  handsConflict: handsConflictSpy,
}))
vi.mock('@/components/character/HandsConflictDialog', async () => {
  const React = await import('react')
  return {
    default: (p: { onConfirm: () => void; onCancel: () => void }) =>
      React.createElement(
        'div',
        { 'data-testid': 'hands-conflict' },
        React.createElement('button', { 'data-testid': 'hc-confirm', onClick: p.onConfirm }, 'confirm'),
        React.createElement('button', { 'data-testid': 'hc-cancel', onClick: p.onCancel }, 'cancel'),
      ),
  }
})

const sword = { id: 1, name: 'Sword', item_type: 'weapon', is_equipped: false, weight: 3, quantity: 1, item_metadata: { weapon_type: 'martial' } } as Item
const dagger = { id: 2, name: 'Dagger', item_type: 'weapon', is_equipped: false, weight: 1, quantity: 1, item_metadata: { weapon_type: 'simple' } } as Item
const shield = { id: 3, name: 'Shield', item_type: 'shield', is_equipped: false, weight: 6, quantity: 1 } as Item
const plate = { id: 4, name: 'Plate', item_type: 'armor', is_equipped: false, weight: 13, quantity: 1 } as Item

afterEach(() => {
  updateSpy.mockReset()
  handsConflictSpy.mockReset()
  navigateSpy.mockReset()
})

describe('EquipItemPicker', () => {
  it('lists only items whose type is compatible with the slot', () => {
    handsConflictSpy.mockReturnValue(null)
    renderWithProviders(<EquipItemPicker charId={42} slot="off_hand" items={[sword, shield, plate]} onClose={() => {}} />)
    expect(screen.getByText('Sword')).toBeInTheDocument()
    expect(screen.getByText('Shield')).toBeInTheDocument()
    expect(screen.queryByText('Plate')).not.toBeInTheDocument() // armor → only the body slot
  })

  it('equipping with no conflict PATCHes is_equipped:true with the target slot, then closes (contract)', async () => {
    handsConflictSpy.mockReturnValue(null)
    updateSpy.mockResolvedValue({ id: 42 })
    const onClose = vi.fn()
    renderWithProviders(<EquipItemPicker charId={42} slot="off_hand" items={[sword]} onClose={onClose} />)
    await userEvent.click(screen.getByText('Sword'))
    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith(42, 1, { is_equipped: true, equipment_slot: 'off_hand' }))
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
  })

  it('a hands conflict opens the confirm dialog; confirming unequips the old item then equips the new one', async () => {
    handsConflictSpy.mockReturnValue(shield) // picking the sword conflicts with the equipped shield
    updateSpy.mockResolvedValue({ id: 42 })
    renderWithProviders(<EquipItemPicker charId={42} slot="off_hand" items={[sword, shield]} onClose={() => {}} />)
    await userEvent.click(screen.getByText('Sword'))
    expect(screen.getByTestId('hands-conflict')).toBeInTheDocument()
    expect(updateSpy).not.toHaveBeenCalled() // not equipped yet
    await userEvent.click(screen.getByTestId('hc-confirm'))
    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith(42, 3, { is_equipped: false, equipment_slot: null }))
    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith(42, 1, { is_equipped: true, equipment_slot: 'off_hand' }))
  })

  it('shows an empty state with a shortcut to the inventory when nothing is compatible', async () => {
    handsConflictSpy.mockReturnValue(null)
    const onClose = vi.fn()
    renderWithProviders(<EquipItemPicker charId={42} slot="off_hand" items={[plate]} onClose={onClose} />)
    expect(screen.getByText('character.equipment.picker.empty')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /character.equipment.picker.go_to_inventory/ }))
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(navigateSpy).toHaveBeenCalledWith('/char/42/inventory')
  })

  it('renders weapon facet filters when ≥2 weapon types exist, and filtering narrows the list', async () => {
    handsConflictSpy.mockReturnValue(null)
    renderWithProviders(<EquipItemPicker charId={42} slot="off_hand" items={[sword, dagger]} onClose={() => {}} />)
    expect(screen.getByText('Sword')).toBeInTheDocument()
    expect(screen.getByText('Dagger')).toBeInTheDocument()
    // toggle the "martial" weapon_type facet → the simple dagger drops out
    await userEvent.click(screen.getByRole('button', { name: 'character.inventory.weapon_type.martial' }))
    expect(screen.getByText('Sword')).toBeInTheDocument()
    expect(screen.queryByText('Dagger')).not.toBeInTheDocument()
  })
})

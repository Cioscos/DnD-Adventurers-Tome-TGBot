import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../../utils/renderWithProviders'
import InventoryItem from '@/pages/inventory/InventoryItem'
import type { Item } from '@/types'

vi.mock('@/api/client', () => ({ api: {}, ApiError: class extends Error {} }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string, o?: Record<string, unknown>) => (o?.defaultValue as string) ?? (o ? `${k} ${JSON.stringify(o)}` : k), i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/store/unitSettings', () => ({
  useUnitSettings: (sel: (s: { system: string }) => unknown) => sel({ system: 'imperial' }),
  formatWeight: (v: number) => `${v} lb`,
  formatLength: (v: number) => `${v} ft`,
}))

const noop = () => undefined
const axe = (over: Partial<Item> = {}): Item => ({
  id: 1, name: 'Ascia bipenne', item_type: 'weapon', weight: 7, quantity: 1, is_equipped: true,
  item_metadata: { damage_dice: '1d12', weapon_type: 'melee', properties: ['heavy'] }, ...over,
} as Item)

function show(item: Item) {
  return renderWithProviders(
    <InventoryItem item={item} isExpanded onToggle={noop} onEquipToggle={noop} onQuantityChange={noop} onAttack={noop}
      weaponChoice={{ mode: 'melee', grip: 'one' } as never} onWeaponChoice={noop} onUse={noop} onEdit={noop} onDelete={noop}
      equipPending={false} attackPending={false} usePending={false} quantityPending={false} sharePending={false}
      propertyByKey={new Map()} locale="it" onSetProperty={noop} setPropertyPending={false} />,
  )
}

describe('InventoryItem reach', () => {
  it('shows the reach a feature adds to the weapon, and nothing without it', () => {
    show(axe({ reach_bonus_ft: 10 }))
    expect(screen.getByText(/character\.inventory\.reach_bonus/)).toBeInTheDocument()
  })

  it('has no reach chip without the bonus', () => {
    show(axe())
    expect(screen.queryByText(/character\.inventory\.reach_bonus/)).toBeNull()
  })
})

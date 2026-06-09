import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ItemDetailsModal from '@/components/character/ItemDetailsModal'
import type { Item } from '@/types'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
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
vi.mock('@/pages/inventory/itemMetadata', () => ({ TYPE_ICON: new Proxy({}, { get: () => '🗡' }) }))

const mk = (over: Partial<Item>): Item =>
  ({ id: 1, name: 'Item', item_type: 'generic', is_equipped: true, weight: 1, quantity: 1, ...over } as Item)

describe('ItemDetailsModal', () => {
  it('shows weapon stats (damage dice / type / category)', () => {
    render(
      <ItemDetailsModal
        slot="main_hand"
        onClose={() => {}}
        item={mk({ name: 'Longsword', item_type: 'weapon', item_metadata: { damage_dice: '1d8', damage_type: 'slashing', weapon_type: 'martial' } })}
      />,
    )
    expect(screen.getByText('Longsword')).toBeInTheDocument()
    expect(screen.getByText('1d8')).toBeInTheDocument()
    expect(screen.getByText('character.inventory.damage_dice_label')).toBeInTheDocument()
  })

  it('shows armor stats (AC value + stealth disadvantage + strength requirement)', () => {
    render(
      <ItemDetailsModal
        slot="body"
        onClose={() => {}}
        item={mk({ name: 'Plate', item_type: 'armor', item_metadata: { ac_value: 18, armor_type: 'heavy', stealth_disadvantage: true, strength_req: 15 } })}
      />,
    )
    expect(screen.getByText('18')).toBeInTheDocument()
    expect(screen.getByText('character.inventory.stealth_disadvantage_label')).toBeInTheDocument()
    expect(screen.getByText('15')).toBeInTheDocument()
  })

  it('shows a shield AC bonus with a + sign', () => {
    render(
      <ItemDetailsModal slot="off_hand" onClose={() => {}} item={mk({ name: 'Shield', item_type: 'shield', item_metadata: { ac_bonus: 2 } })} />,
    )
    expect(screen.getByText('+2')).toBeInTheDocument()
  })

  it('renders properties, ability modifiers (signed) and effects sections', () => {
    render(
      <ItemDetailsModal
        slot="main_hand"
        onClose={() => {}}
        item={mk({
          name: 'Magic Blade',
          item_type: 'weapon',
          item_metadata: {
            properties: ['finesse'],
            ability_modifiers: [{ ability: 'dexterity', value: 2 }, { ability: 'strength', value: -1 }],
            effects: [{ kind: 'heal', amount: '5' }],
          },
        })}
      />,
    )
    expect(screen.getByText('character.inventory.weapon_properties.finesse')).toBeInTheDocument()
    expect(screen.getByText(/\+2/)).toBeInTheDocument()
    expect(screen.getByText(/-1/)).toBeInTheDocument()
    expect(screen.getByText('character.inventory.use_confirm.heal')).toBeInTheDocument()
  })

  it('closes via the close button', async () => {
    const onClose = vi.fn()
    render(<ItemDetailsModal slot="head" onClose={onClose} item={mk({ name: 'Hat' })} />)
    await userEvent.click(screen.getByRole('button', { name: 'common.close' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})

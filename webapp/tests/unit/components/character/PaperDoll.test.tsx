import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PaperDoll from '@/components/character/PaperDoll'
import type { Item } from '@/types'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
// isTwoHanded is driven by a `two_handed` flag on the fixture so the hide-off-hand
// rule can be exercised without depending on real metadata parsing.
vi.mock('@/lib/equipmentSlots', () => ({
  ALL_SLOTS: ['head', 'neck', 'cloak', 'body', 'hands', 'ring1', 'ring2', 'feet', 'ammunition', 'main_hand', 'off_hand'],
  isTwoHanded: (it: { two_handed?: boolean } | null) => Boolean(it && it.two_handed),
}))
vi.mock('@/components/character/EquipmentSlotCell', async () => {
  const React = await import('react')
  return {
    default: (p: { slot: string; equipped: { name: string } | null; onTap: (e: unknown) => void }) =>
      React.createElement('button', {
        'data-testid': `slot-${p.slot}`,
        'data-equipped': p.equipped?.name ?? '',
        onClick: () => p.onTap(p.equipped),
      }),
  }
})

const item = (over: Partial<Item> & { two_handed?: boolean }): Item =>
  ({ id: 1, name: 'X', item_type: 'armor', is_equipped: true, weight: 1, quantity: 1, ...over } as Item)

const ALL = ['head', 'neck', 'cloak', 'body', 'hands', 'ring1', 'ring2', 'feet', 'ammunition', 'main_hand', 'off_hand']

describe('PaperDoll', () => {
  it('renders all 11 equipment slots and places equipped items in the right slot', () => {
    const items = [item({ id: 1, name: 'Helmet', equipment_slot: 'head' })]
    render(<PaperDoll items={items} onSlotTap={() => {}} />)
    for (const s of ALL) expect(screen.getByTestId(`slot-${s}`)).toBeInTheDocument()
    expect(screen.getByTestId('slot-head')).toHaveAttribute('data-equipped', 'Helmet')
    expect(screen.getByTestId('slot-body')).toHaveAttribute('data-equipped', '')
  })

  it('forwards a slot tap with the slot key and its equipped item', async () => {
    const onSlotTap = vi.fn()
    const sword = item({ id: 2, name: 'Sword', item_type: 'weapon', equipment_slot: 'main_hand' })
    render(<PaperDoll items={[sword]} onSlotTap={onSlotTap} />)
    await userEvent.click(screen.getByTestId('slot-main_hand'))
    expect(onSlotTap).toHaveBeenCalledWith('main_hand', sword)
  })

  it('hides the off-hand slot when a two-handed weapon occupies the main hand and off-hand is empty', () => {
    const greatsword = item({ id: 3, name: 'Greatsword', item_type: 'weapon', equipment_slot: 'main_hand', two_handed: true })
    render(<PaperDoll items={[greatsword]} onSlotTap={() => {}} />)
    expect(screen.getByTestId('slot-main_hand')).toBeInTheDocument()
    expect(screen.queryByTestId('slot-off_hand')).not.toBeInTheDocument()
  })

  it('renders the silhouette image when a URL is given, the SVG fallback otherwise', () => {
    const { rerender } = render(<PaperDoll items={[]} onSlotTap={() => {}} silhouetteUrl="https://x/sil.png" />)
    expect(screen.getByRole('img')).toBeInTheDocument()
    rerender(<PaperDoll items={[]} onSlotTap={() => {}} silhouetteUrl={null} />)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('renders the optional silhouette action affordance', () => {
    render(<PaperDoll items={[]} onSlotTap={() => {}} silhouetteAction={<button>upload</button>} />)
    expect(screen.getByRole('button', { name: 'upload' })).toBeInTheDocument()
  })
})

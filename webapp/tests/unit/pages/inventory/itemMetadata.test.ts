import { describe, it, expect } from 'vitest'
import { ITEM_TYPES, TYPE_ICON, hasSingleQuantity, itemToFormData, emptyForm, buildItemMetadata, isItemFormValid } from '@/pages/inventory/itemMetadata'
import type { Item } from '@/types'

describe('itemMetadata — ammunition', () => {
  it('ITEM_TYPES contains ammunition, with icon and multi quantity', () => {
    expect(ITEM_TYPES).toContain('ammunition')
    expect(TYPE_ICON.ammunition).toBeTruthy()
    expect(hasSingleQuantity('ammunition')).toBe(false)
  })

  it('itemToFormData round-trips the ammunition type', () => {
    const item = { id: 1, name: 'Frecce', item_type: 'ammunition', quantity: 20, weight: 0, description: '', item_metadata: null } as unknown as Item
    expect(itemToFormData(item).item_type).toBe('ammunition')
  })
})

describe('INVENTORY_TYPE_ORDER', () => {
  it('gives every item type (ammunition included) its own group, with a label', async () => {
    const { INVENTORY_TYPE_ORDER } = await import('@/pages/inventory/itemMetadata')
    const en = (await import('@/locales/en.json')).default as any
    for (const t of ITEM_TYPES) expect(INVENTORY_TYPE_ORDER).toContain(t)
    expect(en.character.inventory.types.ammunition).toBeTruthy()
  })
})

describe('weapon magic fields', () => {
  const base = { ...emptyForm, name: 'Spada', item_type: 'weapon' as const }
  it('serialises magic_bonus, versatile_dice and weapon_category only when set', () => {
    expect(buildItemMetadata(base)).not.toHaveProperty('magic_bonus')
    const meta = buildItemMetadata({
      ...base, magic_bonus: '2', versatile_dice: '1d10', weapon_category: 'martial',
      properties: ['prop_versatile'],
    })
    expect(meta).toMatchObject({ magic_bonus: 2, versatile_dice: '1d10', weapon_category: 'martial' })
    // versatile die dropped when the property is off
    expect(buildItemMetadata({ ...base, versatile_dice: '1d10' })).not.toHaveProperty('versatile_dice')
  })
  it('rejects out-of-range bonus and bad versatile die', () => {
    expect(isItemFormValid({ ...base, magic_bonus: '11' })).toBe(false)
    expect(isItemFormValid({ ...base, magic_bonus: '3' })).toBe(true)
    expect(isItemFormValid({ ...base, properties: ['prop_versatile'], versatile_dice: 'x' })).toBe(false)
  })
  it('round-trips through itemToFormData', () => {
    const f = itemToFormData({
      name: 'S', item_type: 'weapon', quantity: 1, weight: 0,
      item_metadata: { magic_bonus: 1, versatile_dice: '1d10', weapon_category: 'simple' },
    })
    expect(f).toMatchObject({ magic_bonus: '1', versatile_dice: '1d10', weapon_category: 'simple' })
  })
})

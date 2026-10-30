import { describe, it, expect } from 'vitest'
import { ITEM_TYPES, TYPE_ICON, hasSingleQuantity, itemToFormData } from '@/pages/inventory/itemMetadata'
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

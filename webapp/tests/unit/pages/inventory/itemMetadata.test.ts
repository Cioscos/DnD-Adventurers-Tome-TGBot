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

describe('magic item fields', () => {
  const item = {
    id: 1, name: 'Bacchetta', item_type: 'generic', quantity: 1, weight: 1, description: '',
    item_metadata: {
      hb_enchanted: true, custom_key: { a: 1 }, rarity: 'rare', is_magic: true,
      requires_attunement: true, attuned: true,
      bonuses: [{ target: 'ac', value: 1 }],
      charges: { max: 7, current: 5, recharge: 'dawn', recharge_amount: '1d6+1' },
      granted_spells: [{ name: 'Dardo', level: 1, charges_cost: 1, is_concentration: false, srd_index: 'magic-missile' }],
    },
  } as unknown as Item

  it('keeps unknown pre-existing keys and rewrites the magic ones', () => {
    const form = itemToFormData(item)
    expect(form.rarity).toBe('rare')
    const meta = buildItemMetadata({ ...form, bonuses: [{ target: 'speed', value: 10 }] })!
    expect(meta.hb_enchanted).toBe(true)
    expect(meta.custom_key).toEqual({ a: 1 })
    expect(meta.bonuses).toEqual([{ target: 'speed', value: 10 }])
    expect(meta.charges).toEqual({ max: 7, current: 5, recharge: 'dawn', recharge_amount: '1d6+1' })
    expect((meta.granted_spells as { srd_index: string }[])[0].srd_index).toBe('magic-missile')
    expect(meta.attuned).toBe(true)
  })

  it('drops cleared magic fields and never attunes without requires_attunement', () => {
    const form = itemToFormData(item)
    const meta = buildItemMetadata({ ...form, charges: null, bonuses: [], granted_spells: [], requires_attunement: false })!
    expect(meta).not.toHaveProperty('charges')
    expect(meta).not.toHaveProperty('bonuses')
    expect(meta).not.toHaveProperty('granted_spells')
    expect(meta).not.toHaveProperty('attuned')
    expect(meta.hb_enchanted).toBe(true)
  })

  it('omits all magic keys when the item is not magic, and clamps current to max', () => {
    const form = itemToFormData(item)
    const plain = buildItemMetadata({ ...form, is_magic: false })!
    expect(plain).not.toHaveProperty('rarity')
    expect(plain).not.toHaveProperty('charges')
    const clamped = buildItemMetadata({ ...form, charges: { max: 3, current: 9, recharge: 'none', recharge_amount: 'all' } })!
    expect((clamped.charges as { current: number }).current).toBe(3)
  })

  it('validates charges and granted spells', () => {
    const form = itemToFormData(item)
    expect(isItemFormValid(form)).toBe(true)
    expect(isItemFormValid({ ...form, charges: { max: 0, current: 0, recharge: 'none', recharge_amount: 'all' } })).toBe(false)
    expect(isItemFormValid({ ...form, charges: { ...form.charges!, recharge_amount: 'lots' } })).toBe(false)
    expect(isItemFormValid({ ...form, granted_spells: [{ ...form.granted_spells[0], name: ' ' }] })).toBe(false)
    expect(isItemFormValid({ ...form, granted_spells: [{ ...form.granted_spells[0], charges_cost: 8 }] })).toBe(false)
  })
})

import { describe, it, expect } from 'vitest'
import {
  loadCatalog, equipmentToForm, magicItemToForm, type EquipmentEntry, type MagicItemEntry,
} from '@/lib/srd/catalog'

const eq = async (i: string) => (await loadCatalog('equipment')).find((e) => e.index === i) as EquipmentEntry
const mi = async (i: string) => (await loadCatalog('magic-items')).find((e) => e.index === i) as MagicItemEntry

describe('item catalogue mapping', () => {
  it('longsword', async () => {
    expect(equipmentToForm(await eq('longsword'), 'it', 'imperial')).toMatchObject({
      name: 'Spada lunga', item_type: 'weapon', damage_dice: '1d8', damage_type: 'dmg_slashing',
      versatile_dice: '1d10', weapon_category: 'martial', properties: ['prop_versatile'], weight: '3',
      extra_meta: { srd_index: 'longsword' },
    })
  })
  it('chain mail', async () => {
    expect(equipmentToForm(await eq('chain-mail'), 'en', 'imperial')).toMatchObject({
      item_type: 'armor', armor_type: 'heavy', ac_value: '16', strength_req: '13', stealth_disadvantage: true,
    })
  })
  it('shield and flat-damage blowgun do not crash', async () => {
    expect(equipmentToForm(await eq('shield'), 'en', 'imperial')).toMatchObject({ item_type: 'shield', ac_bonus: '2' })
    const b = equipmentToForm(await eq('blowgun'), 'en', 'imperial')
    expect(b.damage_dice).toBe('1d1')
    expect(b.description).toContain('25 ft')
  })
  it('cloak of protection', async () => {
    expect(magicItemToForm(await mi('cloak-of-protection'), 'en')).toMatchObject({
      is_magic: true, rarity: 'uncommon', requires_attunement: true,
      bonuses: [{ target: 'ac', value: 1 }, { target: 'saves', value: 1 }],
    })
  })
  it('wand of magic missiles', async () => {
    const spells = await loadCatalog('spells')
    const f = magicItemToForm(await mi('wand-of-magic-missiles'), 'en', spells)
    expect(f.charges).toEqual({ max: 7, current: 7, recharge: 'dawn', recharge_amount: '1d6+1' })
    expect(f.granted_spells).toEqual([expect.objectContaining({
      name: 'Magic Missile', level: 1, charges_cost: 1, srd_index: 'magic-missile',
    })])
  })
  it('generic +N weapon becomes magic_bonus; very rare uses underscore', async () => {
    expect(magicItemToForm(await mi('weapon-2'), 'en')).toMatchObject({ item_type: 'weapon', magic_bonus: '2', bonuses: [] })
    expect(magicItemToForm(await mi('staff-of-fire'), 'en').rarity).toBe('very_rare')
  })
})

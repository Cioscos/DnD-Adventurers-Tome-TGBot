/** Pure logic — constants, form types, and metadata builder for inventory items. */

export const ITEM_TYPES = ['generic', 'weapon', 'armor', 'shield', 'consumable', 'tool'] as const
export type ItemType = typeof ITEM_TYPES[number]

export const DAMAGE_TYPES = [
  'dmg_slashing', 'dmg_piercing', 'dmg_bludgeoning',
  'dmg_fire', 'dmg_cold', 'dmg_lightning', 'dmg_acid', 'dmg_poison',
  'dmg_necrotic', 'dmg_radiant', 'dmg_force', 'dmg_psychic', 'dmg_thunder', 'dmg_other',
] as const

export const WEAPON_PROPERTIES = [
  'prop_finesse', 'prop_versatile', 'prop_heavy', 'prop_light',
  'prop_thrown', 'prop_two_handed', 'prop_ammunition', 'prop_loading',
  'prop_reach', 'prop_special',
] as const

export const ARMOR_TYPES = ['light', 'medium', 'heavy'] as const
export const WEAPON_TYPES = ['melee', 'ranged'] as const

export const DAMAGE_DICE_RE = /^\d+d\d+([+-]\d+)?$/

export const TYPE_ICON: Record<string, string> = {
  weapon: '\u2694\uFE0F',
  armor: '\uD83D\uDEE1\uFE0F',
  shield: '\uD83D\uDEE1\uFE0F',
  consumable: '\uD83E\uDDEA',
  tool: '\uD83D\uDD27',
  generic: '\uD83D\uDCE6',
  potion: '\uD83E\uDDEA',
  scroll: '\uD83D\uDCDC',
  gear: '\uD83C\uDF92',
  other: '\uD83D\uDCE6',
}

export type ItemFormData = {
  name: string
  item_type: ItemType
  quantity: string
  weight: string
  description: string
  // weapon
  damage_dice: string
  damage_type: string
  weapon_type: string
  properties: string[]
  // armor
  armor_type: string
  ac_value: string
  stealth_disadvantage: boolean
  strength_req: string
  // shield
  ac_bonus: string
  // consumable
  effect: string
  // tool
  tool_type: string
}

export const emptyForm: ItemFormData = {
  name: '',
  item_type: 'generic',
  quantity: '1',
  weight: '0',
  description: '',
  damage_dice: '1d6',
  damage_type: 'dmg_slashing',
  weapon_type: 'melee',
  properties: [],
  armor_type: 'light',
  ac_value: '11',
  stealth_disadvantage: false,
  strength_req: '0',
  ac_bonus: '2',
  effect: '',
  tool_type: '',
}

export function buildItemMetadata(form: ItemFormData): Record<string, unknown> | undefined {
  switch (form.item_type) {
    case 'weapon':
      return {
        damage_dice: form.damage_dice,
        damage_type: form.damage_type,
        weapon_type: form.weapon_type,
        properties: form.properties,
      }
    case 'armor':
      return {
        armor_type: form.armor_type,
        ac_value: Number(form.ac_value) || 10,
        stealth_disadvantage: form.stealth_disadvantage,
        strength_req: Number(form.strength_req) || 0,
      }
    case 'shield':
      return { ac_bonus: Number(form.ac_bonus) || 2 }
    case 'consumable':
      return form.effect ? { effect: form.effect } : undefined
    case 'tool':
      return form.tool_type ? { tool_type: form.tool_type } : undefined
    default:
      return undefined
  }
}

export function isItemFormValid(form: ItemFormData): boolean {
  if (!form.name.trim()) return false
  if (form.item_type === 'weapon' && !DAMAGE_DICE_RE.test(form.damage_dice.trim())) return false
  if (form.item_type === 'armor' && (Number(form.ac_value) < 1 || isNaN(Number(form.ac_value)))) return false
  return true
}

/** Build the form from an existing Item for editing. */
export function itemToFormData(item: { name: string; item_type: string; quantity: number; weight: number; description?: string; item_metadata?: Record<string, unknown> }): ItemFormData {
  const meta = item.item_metadata ?? {}
  return {
    name: item.name,
    item_type: (ITEM_TYPES as readonly string[]).includes(item.item_type) ? item.item_type as ItemType : 'generic',
    quantity: String(item.quantity),
    weight: String(item.weight),
    description: item.description ?? '',
    damage_dice: String(meta.damage_dice ?? '1d6'),
    damage_type: String(meta.damage_type ?? 'dmg_slashing'),
    weapon_type: String(meta.weapon_type ?? 'melee'),
    properties: Array.isArray(meta.properties) ? meta.properties.map(String) : [],
    armor_type: String(meta.armor_type ?? 'light'),
    ac_value: String(meta.ac_value ?? '11'),
    stealth_disadvantage: !!meta.stealth_disadvantage,
    strength_req: String(meta.strength_req ?? '0'),
    ac_bonus: String(meta.ac_bonus ?? '2'),
    effect: String(meta.effect ?? ''),
    tool_type: String(meta.tool_type ?? ''),
  }
}

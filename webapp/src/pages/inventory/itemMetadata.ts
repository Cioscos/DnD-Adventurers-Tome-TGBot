/** Pure logic — constants, form types, and metadata builder for inventory items. */
import type { AbilityModifier } from '@/types'

export const ITEM_TYPES = [
  'weapon', 'armor', 'shield', 'consumable', 'tool',
  'accessory', 'gear', 'potion', 'scroll', 'generic',
] as const
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

/** Tagli di dado standard per le armi 5e (usati dai chip del builder). */
export const DIE_SIZES = [4, 6, 8, 10, 12] as const

export interface ParsedDamageDice {
  count: number
  die: number
  mod: number
  /** True quando il dado parsato non è tra i DIE_SIZES standard (es. d20 homebrew). */
  unknownDie: boolean
}

/**
 * Parsa una notazione "NdX", "NdX+K" o "NdX-K" nei suoi componenti.
 * Su input vuoto o non parsabile ritorna il default 1d6 (mod 0).
 */
export function parseDamageDice(value: string): ParsedDamageDice {
  const m = value.trim().match(/^(\d+)d(\d+)([+-]\d+)?$/i)
  if (!m) {
    return { count: 1, die: 6, mod: 0, unknownDie: false }
  }
  const count = Math.max(1, parseInt(m[1], 10))
  const die = parseInt(m[2], 10)
  const mod = m[3] ? parseInt(m[3], 10) : 0
  const unknownDie = !(DIE_SIZES as readonly number[]).includes(die)
  return { count, die, mod, unknownDie }
}

/**
 * Compone la notazione canonica. Omette il "+0" quando il modificatore è nullo.
 * `mod` negativo include già il segno '-'.
 */
export function serializeDamageDice(count: number, die: number, mod: number): string {
  const base = `${Math.max(1, count)}d${die}`
  if (mod > 0) return `${base}+${mod}`
  if (mod < 0) return `${base}${mod}`
  return base
}

export const TYPE_ICON: Record<string, string> = {
  weapon: '\u2694\uFE0F',
  armor: '\uD83D\uDEE1\uFE0F',
  shield: '\uD83D\uDEE1\uFE0F',
  accessory: '\uD83D\uDC8E',
  consumable: '\uD83E\uDDEA',
  tool: '\uD83D\uDD27',
  generic: '\uD83D\uDCE6',
  potion: '\uD83E\uDDEA',
  scroll: '\uD83D\uDCDC',
  gear: '\uD83C\uDF92',
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
  // ability modifiers (all item types)
  ability_modifiers?: AbilityModifier[]
}

export const emptyForm: ItemFormData = {
  name: '',
  item_type: 'generic',
  // Left empty so the field shows a placeholder hint, not a pre-filled value
  // (project convention: never pre-fill inputs). The submit logic applies the
  // sensible defaults — quantity → 1, weight → 0 — when left blank.
  quantity: '',
  weight: '',
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
  ability_modifiers: [],
}

export function buildItemMetadata(form: ItemFormData): Record<string, unknown> | undefined {
  let meta: Record<string, unknown> | undefined
  switch (form.item_type) {
    case 'weapon':
      meta = {
        damage_dice: form.damage_dice,
        damage_type: form.damage_type,
        weapon_type: form.weapon_type,
        properties: form.properties,
      }
      break
    case 'armor':
      meta = {
        armor_type: form.armor_type,
        ac_value: Number(form.ac_value) || 10,
        stealth_disadvantage: form.stealth_disadvantage,
        strength_req: Number(form.strength_req) || 0,
      }
      break
    case 'shield':
      meta = { ac_bonus: Number(form.ac_bonus) || 2 }
      break
    case 'consumable':
    case 'potion':
    case 'scroll':
      meta = form.effect ? { effect: form.effect } : undefined
      break
    case 'tool':
      meta = form.tool_type ? { tool_type: form.tool_type } : undefined
      break
    default:
      meta = undefined
  }

  // Ability modifiers (all item types)
  if (form.ability_modifiers && form.ability_modifiers.length > 0) {
    meta = { ...(meta ?? {}), ability_modifiers: form.ability_modifiers }
  }

  return meta
}

/**
 * Build the full `item_metadata` object for a homebrew-property PATCH.
 *
 * The backend `PATCH /characters/{id}/items/{item_id}` REPLACES the whole
 * `item_metadata` column (it does `setattr(item, "item_metadata", json.dumps(...))`),
 * so we must always send the complete merged object — never a partial. We spread
 * the item's current metadata and override the single `hb_<key>` entry.
 */
export function buildHomebrewMetadataPatch(
  current: Record<string, unknown> | undefined,
  propKey: string,
  value: unknown,
): Record<string, unknown> {
  return { ...(current ?? {}), [`hb_${propKey}`]: value }
}

export function isItemFormValid(form: ItemFormData): boolean {
  if (!form.name.trim()) return false
  if (form.item_type === 'weapon' && !DAMAGE_DICE_RE.test(form.damage_dice.trim())) return false
  if (form.item_type === 'armor' && (Number(form.ac_value) < 1 || isNaN(Number(form.ac_value)))) return false
  // Weight must be a non-negative number when provided. Empty/0 allowed for
  // weightless items, but negative weight is never valid (would mess up the
  // encumbrance computation on the equipment paper-doll).
  if (form.weight !== '' && (isNaN(Number(form.weight)) || Number(form.weight) < 0)) return false
  if (form.quantity !== '' && (isNaN(Number(form.quantity)) || Number(form.quantity) < 1)) return false
  return true
}

/** Build the form from an existing Item for editing. */
export function itemToFormData(item: { name: string; item_type: string; quantity: number; weight: number; description?: string; item_metadata?: Record<string, unknown> }): ItemFormData {
  const meta = item.item_metadata ?? {}
  const ability_modifiers = (
    (item.item_metadata as Record<string, unknown> | undefined)?.ability_modifiers as AbilityModifier[] | undefined
  ) ?? []
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
    ability_modifiers,
  }
}

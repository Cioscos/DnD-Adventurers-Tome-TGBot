/** Pure logic — constants, form types, and metadata builder for inventory items. */
import type { AbilityModifier } from '@/types'
import {
  MAGIC_KEYS, CHARGE_AMOUNT_RE,
  type Rarity, type ItemBonus, type ItemCharges, type GrantedSpell,
} from '@/lib/itemMagic'

export const ITEM_TYPES = [
  'weapon', 'armor', 'shield', 'consumable', 'tool',
  'accessory', 'gear', 'ammunition', 'generic',
] as const
export type ItemType = typeof ITEM_TYPES[number]

/** Ordine dei gruppi nella pagina inventario (ogni tipo non elencato cade in `generic`). */
export const INVENTORY_TYPE_ORDER = [
  'weapon', 'armor', 'shield', 'consumable', 'tool', 'accessory', 'gear', 'ammunition',
  'potion', 'scroll', 'generic',
] as const

/** Tipi a quantità singola (sempre 1): non mostrano il selettore quantità. */
export const SINGLE_QTY_TYPES = ['weapon', 'armor', 'shield'] as const
export function hasSingleQuantity(itemType: string): boolean {
  return (SINGLE_QTY_TYPES as readonly string[]).includes(itemType)
}

export const CONSUMABLE_SUBTYPES = ['potion', 'scroll', 'food', 'other'] as const
export type ConsumableSubtype = typeof CONSUMABLE_SUBTYPES[number]

export const EFFECT_KINDS = ['heal', 'add_condition', 'remove_condition'] as const
export type EffectKind = typeof EFFECT_KINDS[number]

export const CONDITION_SLUGS = [
  'blinded', 'charmed', 'deafened', 'frightened', 'grappled',
  'incapacitated', 'invisible', 'paralyzed', 'petrified', 'poisoned',
  'prone', 'restrained', 'stunned', 'unconscious',
] as const

export type ItemEffect =
  | { kind: 'heal'; amount: string }
  | { kind: 'add_condition'; condition: string }
  | { kind: 'remove_condition'; condition: string }

/** Heal amount: dice notation (NdX[+/-K]) OR a plain integer. */
export const HEAL_AMOUNT_RE = /^(\d+d\d+([+-]\d+)?|\d+)$/i

export function isEffectValid(e: ItemEffect): boolean {
  if (e.kind === 'heal') return HEAL_AMOUNT_RE.test(e.amount.trim())
  return !!e.condition
}

export function areEffectsValid(effects: ItemEffect[]): boolean {
  return effects.every(isEffectValid)
}

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
  ammunition: '\uD83C\uDFF9',
}

/** Emoji for a consumable based on its subtype (falls back to the consumable icon). */
export function consumableEmoji(subtype: string | undefined): string {
  if (subtype === 'potion') return TYPE_ICON.potion
  if (subtype === 'scroll') return TYPE_ICON.scroll
  if (subtype === 'food') return '\uD83C\uDF56' // meat on bone
  return TYPE_ICON.consumable
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
  /** Bonus magico (+N) come stringa 0-10; vuoto = nessuno. */
  magic_bonus: string
  /** Dado a due mani (arma versatile); vuoto = non impostato. */
  versatile_dice: string
  weapon_category: '' | 'simple' | 'martial'
  // armor
  armor_type: string
  ac_value: string
  stealth_disadvantage: boolean
  strength_req: string
  // shield
  ac_bonus: string
  // consumable
  effect: string
  subtype: string
  effects: ItemEffect[]
  // tool
  tool_type: string
  // ability modifiers (all item types)
  ability_modifiers?: AbilityModifier[]
  // magic (R4)
  is_magic: boolean
  rarity: '' | Rarity
  cost_gp: string
  requires_attunement: boolean
  attuned: boolean
  bonuses: ItemBonus[]
  charges: ItemCharges | null
  granted_spells: GrantedSpell[]
  /** Chiavi di item_metadata non gestite dal form (hb_*, futuri): il PATCH sostituisce tutto, vanno rimandate. */
  extra_meta: Record<string, unknown>
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
  magic_bonus: '',
  versatile_dice: '',
  weapon_category: '',
  armor_type: 'light',
  ac_value: '11',
  stealth_disadvantage: false,
  strength_req: '0',
  ac_bonus: '2',
  effect: '',
  subtype: 'other',
  effects: [],
  tool_type: '',
  ability_modifiers: [],
  is_magic: false,
  rarity: '',
  cost_gp: '',
  requires_attunement: false,
  attuned: false,
  bonuses: [],
  charges: null,
  granted_spells: [],
  extra_meta: {},
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
      if (Number(form.magic_bonus) > 0) meta.magic_bonus = Number(form.magic_bonus)
      if (form.properties.includes('prop_versatile') && form.versatile_dice.trim()) {
        meta.versatile_dice = form.versatile_dice.trim()
      }
      if (form.weapon_category) meta.weapon_category = form.weapon_category
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
    case 'consumable': {
      const m: Record<string, unknown> = { subtype: form.subtype }
      if (form.effect) m.effect = form.effect
      if (form.effects && form.effects.length > 0) m.effects = form.effects
      meta = m
      break
    }
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

  if (form.is_magic) {
    const magic: Record<string, unknown> = { is_magic: true }
    if (form.rarity) magic.rarity = form.rarity
    if (form.cost_gp.trim() !== '' && Number(form.cost_gp) >= 0) magic.cost_gp = Number(form.cost_gp)
    if (form.requires_attunement) {
      magic.requires_attunement = true
      if (form.attuned) magic.attuned = true
    }
    if (form.bonuses.length > 0) magic.bonuses = form.bonuses
    if (form.charges) {
      magic.charges = { ...form.charges, current: Math.min(form.charges.current, form.charges.max) }
    }
    if (form.granted_spells.length > 0) {
      // CD/attacco dell'oggetto: vuoti = non impostati, quindi omessi.
      magic.granted_spells = form.granted_spells.map(({ save_dc, attack_bonus, ...rest }) => ({
        ...rest,
        ...(save_dc != null ? { save_dc } : {}),
        ...(attack_bonus != null ? { attack_bonus } : {}),
      }))
    }
    meta = { ...(meta ?? {}), ...magic }
  }

  const merged = { ...(form.extra_meta ?? {}), ...(meta ?? {}) }
  return Object.keys(merged).length > 0 ? merged : undefined
}

/** Build the full `item_metadata` object for a homebrew-property PATCH.
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
  if (form.item_type === 'weapon') {
    const mb = form.magic_bonus.trim()
    if (mb !== '' && !(Number.isInteger(Number(mb)) && Number(mb) >= 0 && Number(mb) <= 10)) return false
    if (form.properties.includes('prop_versatile') && form.versatile_dice.trim() !== ''
      && !DAMAGE_DICE_RE.test(form.versatile_dice.trim())) return false
  }
  if (form.item_type === 'armor' && (Number(form.ac_value) < 1 || isNaN(Number(form.ac_value)))) return false
  // Weight must be a non-negative number when provided. Empty/0 allowed for
  // weightless items, but negative weight is never valid (would mess up the
  // encumbrance computation on the equipment paper-doll).
  if (form.weight !== '' && (isNaN(Number(form.weight)) || Number(form.weight) < 0)) return false
  if (form.quantity !== '' && (isNaN(Number(form.quantity)) || Number(form.quantity) < 1)) return false
  if (form.item_type === 'consumable' && !areEffectsValid(form.effects ?? [])) return false
  if (form.is_magic) {
    const c = form.charges
    if (c) {
      if (!Number.isInteger(c.max) || c.max < 1 || c.max > 100) return false
      if (!Number.isInteger(c.current) || c.current < 0) return false
      if (!CHARGE_AMOUNT_RE.test(c.recharge_amount.trim())) return false
    }
    const cap = c?.max ?? 0
    for (const g of form.granted_spells) {
      if (!g.name.trim() || g.charges_cost < 0 || g.charges_cost > cap) return false
      if (!Number.isInteger(g.level) || g.level < 0 || g.level > 9) return false
    }
  }
  return true
}

/** Chiavi che il form riscrive da sé: tutte le altre finiscono in `extra_meta`. */
const FORM_OWNED_KEYS = new Set<string>([
  'damage_dice', 'damage_type', 'weapon_type', 'properties', 'magic_bonus', 'versatile_dice',
  'weapon_category', 'armor_type', 'ac_value', 'stealth_disadvantage', 'strength_req', 'ac_bonus',
  'subtype', 'effect', 'effects', 'tool_type', 'ability_modifiers', ...MAGIC_KEYS,
])

/** Build the form from an existing Item for editing. */
export function itemToFormData(item: { name: string; item_type: string; quantity: number; weight: number; description?: string; item_metadata?: Record<string, unknown> }): ItemFormData {
  const meta = item.item_metadata ?? {}
  const ability_modifiers = (
    (item.item_metadata as Record<string, unknown> | undefined)?.ability_modifiers as AbilityModifier[] | undefined
  ) ?? []
  return {
    name: item.name,
    item_type: (ITEM_TYPES as readonly string[]).includes(item.item_type)
      ? (item.item_type as ItemType)
      : (item.item_type === 'potion' || item.item_type === 'scroll' ? 'consumable' : 'generic'),
    quantity: String(item.quantity),
    weight: String(item.weight),
    description: item.description ?? '',
    damage_dice: String(meta.damage_dice ?? '1d6'),
    damage_type: String(meta.damage_type ?? 'dmg_slashing'),
    weapon_type: String(meta.weapon_type ?? 'melee'),
    properties: Array.isArray(meta.properties) ? meta.properties.map(String) : [],
    magic_bonus: meta.magic_bonus ? String(meta.magic_bonus) : '',
    versatile_dice: meta.versatile_dice ? String(meta.versatile_dice) : '',
    weapon_category: meta.weapon_category === 'simple' || meta.weapon_category === 'martial' ? meta.weapon_category : '',
    armor_type: String(meta.armor_type ?? 'light'),
    ac_value: String(meta.ac_value ?? '11'),
    stealth_disadvantage: !!meta.stealth_disadvantage,
    strength_req: String(meta.strength_req ?? '0'),
    ac_bonus: String(meta.ac_bonus ?? '2'),
    effect: String(meta.effect ?? ''),
    subtype: typeof meta.subtype === 'string'
      ? meta.subtype
      : (item.item_type === 'potion' || item.item_type === 'scroll' ? item.item_type : 'other'),
    effects: Array.isArray(meta.effects) ? (meta.effects as ItemEffect[]) : [],
    tool_type: String(meta.tool_type ?? ''),
    ability_modifiers,
    is_magic: !!meta.is_magic || MAGIC_KEYS.some((k) => k !== 'is_magic' && meta[k] != null && meta[k] !== false),
    rarity: typeof meta.rarity === 'string' ? (meta.rarity as Rarity) : '',
    cost_gp: meta.cost_gp != null ? String(meta.cost_gp) : '',
    requires_attunement: !!meta.requires_attunement,
    attuned: !!meta.attuned,
    bonuses: Array.isArray(meta.bonuses) ? (meta.bonuses as ItemBonus[]) : [],
    charges: meta.charges && typeof meta.charges === 'object' ? (meta.charges as ItemCharges) : null,
    granted_spells: Array.isArray(meta.granted_spells) ? (meta.granted_spells as GrantedSpell[]) : [],
    extra_meta: Object.fromEntries(
      Object.entries(meta).filter(([k]) => !FORM_OWNED_KEYS.has(k)),
    ),
  }
}

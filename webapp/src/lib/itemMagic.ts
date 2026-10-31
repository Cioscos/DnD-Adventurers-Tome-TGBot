/** Campi magici di `item_metadata` (contratto api/schemas/item_magic.py). */
import type { Item } from '@/types'

export const RARITIES = ['common', 'uncommon', 'rare', 'very_rare', 'legendary', 'artifact'] as const
export type Rarity = typeof RARITIES[number]

const ABILITIES = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma'] as const
export const BONUS_TARGETS = [
  'ac', 'saves', ...ABILITIES.map((a) => `save.${a}`),
  'attack', 'damage', 'spell_attack', 'spell_dc', 'speed', 'initiative',
] as const

export const RECHARGES = ['long_rest', 'short_rest', 'dawn', 'none'] as const
export type Recharge = typeof RECHARGES[number]

export interface ItemBonus { target: string; value: number }
export interface ItemCharges { max: number; current: number; recharge: Recharge; recharge_amount: string }
export interface GrantedSpell {
  name: string
  level: number
  charges_cost: number
  is_concentration: boolean
  duration?: string | null
  srd_index?: string | null
  save_dc?: number | null
  attack_bonus?: number | null
}

/** Chiavi magiche gestite dal form: tutto il resto di `item_metadata` va preservato. */
export const MAGIC_KEYS = [
  'rarity', 'is_magic', 'cost_gp', 'requires_attunement', 'attuned',
  'bonuses', 'charges', 'granted_spells',
] as const

export const MAX_ATTUNED = 3
export const CHARGE_AMOUNT_RE = /^(all|\d{1,2}d\d{1,3}([+-]\d{1,3})?)$/i

const meta = (item: Item): Record<string, unknown> => (item.item_metadata ?? {}) as Record<string, unknown>

export function itemCharges(item: Item): ItemCharges | null {
  const c = meta(item).charges as Partial<ItemCharges> | undefined | null
  return c && typeof c.max === 'number' ? (c as ItemCharges) : null
}

export function itemGrantedSpells(item: Item): GrantedSpell[] {
  const g = meta(item).granted_spells
  return Array.isArray(g) ? (g as GrantedSpell[]) : []
}

export function itemRarity(item: Item): Rarity | null {
  const r = meta(item).rarity
  return (RARITIES as readonly string[]).includes(r as string) ? (r as Rarity) : null
}

export const requiresAttunement = (item: Item) => !!meta(item).requires_attunement
export const isAttuned = (item: Item) => !!meta(item).attuned

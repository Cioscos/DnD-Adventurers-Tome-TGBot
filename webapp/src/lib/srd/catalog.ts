import { formatLength, type UnitSystem } from '@/store/unitSettings'
import type { SpellFormData } from '@/pages/spells/SpellForm'
import type { ItemFormData } from '@/pages/inventory/itemMetadata'
import type { ItemBonus, Recharge } from '@/lib/itemMagic'

export type CatalogKind =
  'spells' | 'magic-items' | 'equipment' | 'races' | 'backgrounds' | 'feats' | 'monsters'
export type Lang = 'it' | 'en'
export interface LocalizedField { en: string; it?: string }

export interface BaseEntry {
  index: string
  name: LocalizedField
  [key: string]: unknown
}

export interface SpellEntry extends BaseEntry {
  level: number
  school: string
  casting_time: LocalizedField
  range_ft: number | null
  range_text: LocalizedField
  area: { type: string; size_ft: number } | null
  components: string[]
  material?: LocalizedField
  duration: LocalizedField
  concentration: boolean
  ritual: boolean
  desc: LocalizedField
  higher_level?: LocalizedField
  attack_type: 'ATK' | 'SAVE' | null
  save_ability: string | null
  damage_dice: string | null
  damage_type: string | null
  higher_levels_dice: string | null
}

export interface EquipmentEntry extends BaseEntry {
  weight_lb: number
  // weapons
  damage_dice?: string
  damage_type?: string
  weapon_category?: 'simple' | 'martial'
  weapon_range?: 'melee' | 'ranged'
  properties?: string[]
  versatile_dice?: string | null
  range_ft?: number | null
  thrown_range_ft?: number | null
  // armor / shield
  armor_type?: 'light' | 'medium' | 'heavy' | 'shield'
  ac_value?: number
  strength_req?: number
  stealth_disadvantage?: boolean
}

export interface MagicItemEntry extends BaseEntry {
  rarity: string
  requires_attunement: boolean
  category: string
  desc: LocalizedField
  charges: { max: number; recharge: Recharge; recharge_dice: string | null } | null
  bonuses: ItemBonus[]
  granted_spells: { spell: string; charge_cost: number }[]
}

export interface MonsterAction {
  name: LocalizedField
  desc: LocalizedField
  attack_bonus: number | null
  damage_dice: string | null
  damage_type: string | null
}

export interface MonsterEntry extends BaseEntry {
  size: string
  type: string
  armor_class: number
  hit_points: number
  speed: Record<string, number>
  abilities: Record<string, number>
  challenge_rating: number
  traits: { name: LocalizedField; desc: LocalizedField }[]
  actions: MonsterAction[]
}

export interface KindEntries {
  spells: SpellEntry
  'magic-items': MagicItemEntry
  equipment: EquipmentEntry
  races: BaseEntry
  backgrounds: BaseEntry
  feats: BaseEntry
  monsters: MonsterEntry
}
export type CatalogEntry<K extends CatalogKind> = KindEntries[K]

const LOADERS: Record<CatalogKind, () => Promise<{ default: { items: unknown[] } }>> = {
  spells: () => import('@/data/srd/spells.json'),
  'magic-items': () => import('@/data/srd/magic-items.json'),
  equipment: () => import('@/data/srd/equipment.json'),
  races: () => import('@/data/srd/races.json'),
  backgrounds: () => import('@/data/srd/backgrounds.json'),
  feats: () => import('@/data/srd/feats.json'),
  monsters: () => import('@/data/srd/monsters.json'),
}

const cache = new Map<CatalogKind, Promise<unknown[]>>()

export function loadCatalog<K extends CatalogKind>(kind: K): Promise<CatalogEntry<K>[]> {
  let p = cache.get(kind)
  if (!p) {
    p = LOADERS[kind]().then((m) => m.default.items)
    cache.set(kind, p)
  }
  return p as Promise<CatalogEntry<K>[]>
}

/** it falls back to en (flagged) when the translation is missing. */
export function localized(
  field: LocalizedField | null | undefined,
  lang: Lang,
): { text: string; fallback: boolean } {
  if (!field) return { text: '', fallback: false }
  if (lang === 'it') {
    return field.it ? { text: field.it, fallback: false } : { text: field.en, fallback: true }
  }
  return { text: field.en, fallback: false }
}

const norm = (s: string) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()

/** Accent/case-insensitive match on the name in both languages (and the index). */
export function searchCatalog<E extends BaseEntry>(entries: E[], query: string, _lang?: Lang): E[] {
  const q = norm(query.trim())
  if (!q) return entries
  return entries.filter((e) =>
    norm(e.name.en).includes(q) || norm(e.name.it ?? '').includes(q) || e.index.includes(q))
}

const AREA_LABEL: Record<string, LocalizedField> = {
  sphere: { en: 'sphere', it: 'sfera' },
  cone: { en: 'cone', it: 'cono' },
  cube: { en: 'cube', it: 'cubo' },
  line: { en: 'line', it: 'linea' },
  cylinder: { en: 'cylinder', it: 'cilindro' },
  square: { en: 'square', it: 'quadrato' },
}

/** Sleep's higher-level dice are an HP pool, not damage: never prefilled. */
const NO_UPCAST_PREFILL = new Set(['sleep'])

export function spellToForm(
  e: SpellEntry,
  lang: Lang,
  unitSystem: UnitSystem,
): Partial<SpellFormData> {
  let range = e.range_ft != null ? formatLength(e.range_ft, unitSystem) : localized(e.range_text, lang).text
  if (e.area) {
    const kind = AREA_LABEL[e.area.type]?.[lang] ?? e.area.type
    range += ` (${kind} ${formatLength(e.area.size_ft, unitSystem)})`
  }
  const mat = e.material ? localized(e.material, lang).text.replace(/\.$/, '') : ''
  const comps = e.components.join(', ') + (mat && e.components.includes('M') ? ` (${mat})` : '')
  return {
    name: localized(e.name, lang).text,
    level: String(e.level),
    description: localized(e.desc, lang).text,
    casting_time: localized(e.casting_time, lang).text,
    range_area: range,
    components: comps,
    duration: localized(e.duration, lang).text,
    is_concentration: e.concentration,
    is_ritual: e.ritual,
    higher_level: localized(e.higher_level, lang).text,
    damage_dice: e.damage_dice ?? '',
    damage_type: e.damage_type ?? '',
    // Spells with damage but no attack_type (magic missile, sleep) stay "none".
    attack_save: e.attack_type ?? '',
    school: e.school,
    srd_index: e.index,
    higher_levels_dice: e.damage_dice && !NO_UPCAST_PREFILL.has(e.index) ? e.higher_levels_dice ?? '' : '',
  }
}

/**
 * Extra dice the server adds automatically for casting above the spell's level
 * (mirror of roll_damage in api/routers/spells.py: same sides only, never sleep).
 */
export function upcastExtraDice(
  spell: { level: number; srd_index?: string | null; higher_levels_dice?: string | null },
  castingLevel: number,
  baseSides: number,
): number {
  const m = /^(\d+)d(\d+)$/.exec(spell.higher_levels_dice?.trim() ?? '')
  if (!m || spell.level < 1 || NO_UPCAST_PREFILL.has(spell.srd_index ?? '') || Number(m[2]) !== baseSides) return 0
  return Number(m[1]) * Math.max(0, castingLevel - spell.level)
}

/** Localised labels for the range note, supplied by the caller (i18n lives in the locale files). */
export interface RangeLabels { range: string; thrown: string }

export function equipmentToForm(
  e: EquipmentEntry,
  lang: Lang,
  unitSystem: UnitSystem,
  labels: RangeLabels,
): Partial<ItemFormData> {
  const base = {
    name: localized(e.name, lang).text,
    weight: String(e.weight_lb),
    extra_meta: { srd_index: e.index },
  }
  if (e.armor_type === 'shield') {
    return { ...base, item_type: 'shield', ac_bonus: String(e.ac_value ?? 2) }
  }
  if (e.armor_type) {
    return {
      ...base, item_type: 'armor', armor_type: e.armor_type, ac_value: String(e.ac_value ?? 10),
      stealth_disadvantage: !!e.stealth_disadvantage, strength_req: String(e.strength_req ?? 0),
    }
  }
  const notes = [
    e.range_ft && e.weapon_range === 'ranged' ? `${labels.range}: ${formatLength(e.range_ft, unitSystem)}` : '',
    e.thrown_range_ft ? `${labels.thrown}: ${formatLength(e.thrown_range_ft, unitSystem)}` : '',
  ].filter(Boolean)
  // shortcut: flat damage ("1", blowgun) becomes "1d1" to satisfy the NdX form rule; revisit if flat damage is supported.
  const dice = e.damage_dice ?? '1d6'
  return {
    ...base, item_type: 'weapon',
    damage_dice: /^\d+$/.test(dice) ? `${dice}d1` : dice,
    damage_type: `dmg_${e.damage_type ?? 'slashing'}`,
    weapon_type: e.weapon_range ?? 'melee',
    properties: e.properties ?? [],
    versatile_dice: e.versatile_dice ?? '',
    weapon_category: e.weapon_category ?? '',
    description: notes.join(' · '),
  }
}

const MAGIC_ITEM_TYPE: Record<string, ItemFormData['item_type']> = {
  weapon: 'weapon', armor: 'armor', ammunition: 'ammunition', potion: 'consumable', scroll: 'consumable',
  ring: 'accessory', 'wondrous-items': 'accessory',
}

export function magicItemToForm(
  e: MagicItemEntry,
  lang: Lang,
  spells: SpellEntry[] = [],
): Partial<ItemFormData> {
  let bonuses = e.bonuses
  let magic_bonus = ''
  if (e.category === 'weapon') {
    // Generic "Weapon, +N" entries carry equal attack+damage bonuses: that is the weapon's magic_bonus.
    const atk = bonuses.find((b) => b.target === 'attack')
    if (atk && bonuses.some((b) => b.target === 'damage' && b.value === atk.value)) {
      magic_bonus = String(atk.value)
      bonuses = bonuses.filter((b) => b.target !== 'attack' && b.target !== 'damage')
    }
  }
  const granted_spells = e.granted_spells.map((g) => {
    const sp = spells.find((s) => s.index === g.spell)
    return {
      name: sp ? localized(sp.name, lang).text : g.spell,
      level: sp?.level ?? 1,
      charges_cost: g.charge_cost,
      is_concentration: !!sp?.concentration,
      duration: sp ? localized(sp.duration, lang).text : null,
      srd_index: g.spell,
    }
  })
  return {
    name: localized(e.name, lang).text,
    item_type: MAGIC_ITEM_TYPE[e.category] ?? 'generic',
    description: localized(e.desc, lang).text,
    ...(e.category === 'potion' || e.category === 'scroll' ? { subtype: e.category } : {}),
    is_magic: true,
    rarity: e.rarity.replace(' ', '_') as ItemFormData['rarity'],
    requires_attunement: e.requires_attunement,
    magic_bonus,
    bonuses,
    charges: e.charges
      ? { max: e.charges.max, current: e.charges.max, recharge: e.charges.recharge, recharge_amount: e.charges.recharge_dice ?? 'all' }
      : null,
    granted_spells,
    extra_meta: { srd_index: e.index },
  }
}

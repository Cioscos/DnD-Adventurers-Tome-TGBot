/**
 * Frontend mirror of the backend unarmed-strike damage logic
 * (`core/game/attacks.py`, `core/rules/weapons.py`). Kept in sync so the Turn page can describe the
 * *actual* damage the backend will roll instead of a hardcoded "1 + mod".
 */

type Edition = '2014' | '2024'

/** Monk Martial Arts die by monk level: thresholds 1/5/11/17; 2014 d4-d10, 2024 d6-d12. */
export function martialArtsDie(monkLevel: number, edition: Edition = '2014'): string {
  if (monkLevel <= 0) return ''
  const step = Number(monkLevel >= 5) + Number(monkLevel >= 11) + Number(monkLevel >= 17)
  return `1d${(edition === '2024' ? 6 : 4) + 2 * step}`
}

type ClassLike = { class_name: string; level: number }
type ItemLike = { item_type?: string; is_equipped?: boolean; name?: string; item_metadata?: Record<string, unknown> | null }

function hasProperty(item: ItemLike, ...words: string[]): boolean {
  const props = item.item_metadata?.properties
  const listed = (Array.isArray(props) ? props : []).map(String).join(' ').toLowerCase()
  return words.some((w) => listed.includes(w))
}

export const isLight = (item: ItemLike) => hasProperty(item, 'light', 'legger')
export const isFinesse = (item: ItemLike) => hasProperty(item, 'finesse', 'accurat')

export function isMonkWeapon(item: ItemLike, edition: Edition): boolean {
  if (item.item_metadata?.weapon_type === 'ranged') return false
  const category = item.item_metadata?.weapon_category
  if (edition === '2024') return category === 'simple' || (category === 'martial' && isLight(item))
  if (/\b(spada corta|shortsword)\b/i.test(item.name ?? '')) return true
  return category === 'simple' && !hasProperty(item, 'heavy', 'pesant', 'two_handed', 'two-handed', 'due mani')
}

/**
 * Monk level when Martial Arts holds: no armor, no shield, only monk weapons in hand. `class_name` is the
 * stored localized label, so we match both the Italian ("Monaco") and English ("Monk") keys.
 */
export function martialArtsLevel(
  classes: ClassLike[] | undefined, edition: Edition = '2014', items: ItemLike[] = [], weapon?: ItemLike,
): number {
  const level = (classes ?? []).find((c) => ['monaco', 'monk'].includes(c.class_name.trim().toLowerCase()))?.level ?? 0
  const worn = items.filter((i) => i.is_equipped)
  if (worn.some((i) => i.item_type === 'armor' || i.item_type === 'shield')) return 0
  const held = [...worn.filter((i) => i.item_type === 'weapon'), ...(weapon ? [weapon] : [])]
  return held.every((w) => isMonkWeapon(w, edition)) ? level : 0
}

/** Damage dice of the unarmed strike: the Martial Arts die while it holds, otherwise the flat "1". */
export function unarmedDamageDice(
  classes: ClassLike[] | undefined, edition: Edition = '2014', items: ItemLike[] = [],
): string {
  const level = martialArtsLevel(classes, edition, items)
  return level > 0 ? martialArtsDie(level, edition) : '1'
}

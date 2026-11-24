import { isFinesse, isLight } from '@/lib/unarmedStrike'
import type { CharacterFull } from '@/types'

/** Pre-attack choices a weapon offers (versatile grip, thrown attack, other hand, ability). */
export type WeaponChoice = {
  grip: 'one' | 'two'
  attack_mode: 'melee' | 'thrown' | 'offhand'
  /** Solo dove la regola lascia la scelta; senza, il server usa la migliore. */
  ability?: 'strength' | 'dexterity'
}

export const DEFAULT_WEAPON_CHOICE: WeaponChoice = { grip: 'one', attack_mode: 'melee' }

type ItemLike = { id?: number; martial_arts?: boolean; item_metadata?: Record<string, unknown> | null }
export type ChoiceChar = Pick<CharacterFull, 'classes' | 'rules_edition' | 'items' | 'ability_scores'> & Partial<Pick<CharacterFull, 'abilities'>>

function props(item: ItemLike): string[] {
  const p = item.item_metadata?.properties
  return Array.isArray(p) ? p.map(String) : []
}

export function weaponOptions(
  item: ItemLike, char?: ChoiceChar,
): { versatile: boolean; thrown: boolean; offhand: boolean; ability: boolean } {
  const p = props(item)
  const others = char?.items ?? []
  const oneHanded = (o: ItemLike) => !props(o).includes('prop_two_handed') && (o.item_metadata?.weapon_type ?? 'melee') === 'melee'
  // Combattente a Due Armi 2014: armi da mischia a una mano anche non leggere (come `api/routers/items.py`)
  const dualWielder = (char?.abilities ?? []).some((a) => a.feature_key === 'feat.dual_wielder')
  // 2024: basta un'arma da mischia senza Due Mani, dopo un attacco con una leggera
  const dual24 = char?.rules_edition === '2024' && (char.abilities ?? []).some((a) => a.feature_key === 'feat.2024_dual_wielder')
  const second = (ok: (o: ItemLike) => boolean) =>
    others.some((o) => o.id !== item.id && o.item_type === 'weapon' && o.is_equipped && ok(o))
  return {
    versatile: p.includes('prop_versatile') && !!item.item_metadata?.versatile_dice,
    thrown: p.includes('prop_thrown'),
    // 2014: l'altra mano è un'arma da mischia leggera (p.195); nel 2024 basta Leggera (come `api/routers/items.py`)
    offhand: dualWielder ? oneHanded(item) && second(oneHanded)
      : (isLight(item) || (dual24 && oneHanded(item))) && second(isLight) && (char?.rules_edition === '2024' || (item.item_metadata?.weapon_type ?? 'melee') === 'melee'),
    ability: !!char && (isFinesse(item) || !!item.martial_arts),  // Arti Marziali: il server dice se vale per quest'arma
  }
}

/** La caratteristica che il server userebbe senza scelta. */
export function bestAbility(char: ChoiceChar | undefined): 'strength' | 'dexterity' {
  const mod = (name: string) => char?.ability_scores?.find((a) => a.name === name)?.modifier ?? 0
  return mod('dexterity') > mod('strength') ? 'dexterity' : 'strength'
}

/** Gittata normale in ft di un'arma a distanza o da lancio, dal catalogo SRD (per indice o nome it/en); null se non c'è. */
export function weaponRangeFt(
  item: { name?: string; item_metadata?: Record<string, unknown> | null },
  entries: { index: string; name: { en: string; it?: string }; weapon_range?: string; range_ft?: number | null; thrown_range_ft?: number | null }[],
): number | null {
  const meta = item.item_metadata ?? {}
  const ranged = meta.weapon_type === 'ranged'
  if (!ranged && !props(item).includes('prop_thrown')) return null
  const name = (item.name ?? '').trim().toLowerCase()
  const entry = entries.find((e) => e.index === meta.srd_index)
    ?? entries.find((e) => e.name.en.toLowerCase() === name || e.name.it?.toLowerCase() === name)
  return (ranged ? entry?.range_ft : entry?.thrown_range_ft) ?? null
}

/** «+7 · 1d6+4»: bonus per colpire e danno dell'arma con le scelte predefinite (li calcola il server); '' senza anteprima. */
export function weaponPreviewText(item: {
  item_metadata?: Record<string, unknown> | null
  attack_preview?: { to_hit: number; damage: number } | null
}): string {
  const p = item.attack_preview
  if (!p) return ''
  const sign = (n: number) => (n >= 0 ? `+${n}` : `${n}`)
  const dice = String(item.item_metadata?.damage_dice ?? '')
  return `${sign(p.to_hit)} · ${p.damage ? `${dice}${sign(p.damage)}` : dice}`
}

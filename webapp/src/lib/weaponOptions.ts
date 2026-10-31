/** Pre-attack choices a weapon offers (versatile grip, thrown attack). */
export type WeaponChoice = { grip: 'one' | 'two'; attack_mode: 'melee' | 'thrown' }

export const DEFAULT_WEAPON_CHOICE: WeaponChoice = { grip: 'one', attack_mode: 'melee' }

type ItemLike = { item_metadata?: Record<string, unknown> | null }

function props(item: ItemLike): string[] {
  const p = item.item_metadata?.properties
  return Array.isArray(p) ? p.map(String) : []
}

export function weaponOptions(item: ItemLike): { versatile: boolean; thrown: boolean } {
  const p = props(item)
  return {
    versatile: p.includes('prop_versatile') && !!item.item_metadata?.versatile_dice,
    thrown: p.includes('prop_thrown'),
  }
}

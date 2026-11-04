import { isFinesse, isLight, martialArtsLevel } from '@/lib/unarmedStrike'
import type { CharacterFull } from '@/types'

/** Pre-attack choices a weapon offers (versatile grip, thrown attack, other hand, ability). */
export type WeaponChoice = {
  grip: 'one' | 'two'
  attack_mode: 'melee' | 'thrown' | 'offhand'
  /** Solo dove la regola lascia la scelta; senza, il server usa la migliore. */
  ability?: 'strength' | 'dexterity'
}

export const DEFAULT_WEAPON_CHOICE: WeaponChoice = { grip: 'one', attack_mode: 'melee' }

type ItemLike = { id?: number; item_metadata?: Record<string, unknown> | null }
export type ChoiceChar = Pick<CharacterFull, 'classes' | 'rules_edition' | 'items' | 'ability_scores'>

function props(item: ItemLike): string[] {
  const p = item.item_metadata?.properties
  return Array.isArray(p) ? p.map(String) : []
}

export function weaponOptions(
  item: ItemLike, char?: ChoiceChar,
): { versatile: boolean; thrown: boolean; offhand: boolean; ability: boolean } {
  const p = props(item)
  const others = char?.items ?? []
  return {
    versatile: p.includes('prop_versatile') && !!item.item_metadata?.versatile_dice,
    thrown: p.includes('prop_thrown'),
    offhand: isLight(item) && others.some((o) => o.id !== item.id && o.item_type === 'weapon' && o.is_equipped && isLight(o)),
    ability: !!char && (isFinesse(item) || martialArtsLevel(char.classes, char.rules_edition, char.items, item) > 0),
  }
}

/** La caratteristica che il server userebbe senza scelta. */
export function bestAbility(char: ChoiceChar | undefined): 'strength' | 'dexterity' {
  const mod = (name: string) => char?.ability_scores?.find((a) => a.name === name)?.modifier ?? 0
  return mod('dexterity') > mod('strength') ? 'dexterity' : 'strength'
}

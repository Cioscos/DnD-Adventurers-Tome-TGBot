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
  const oneHanded = (o: ItemLike) => !props(o).includes('prop_two_handed')
  // Combattente a Due Armi 2014: armi a una mano anche non leggere (come `api/routers/items.py`)
  const dualWielder = (char?.abilities ?? []).some((a) => a.feature_key === 'feat.dual_wielder')
  const second = (ok: (o: ItemLike) => boolean) =>
    others.some((o) => o.id !== item.id && o.item_type === 'weapon' && o.is_equipped && ok(o))
  return {
    versatile: p.includes('prop_versatile') && !!item.item_metadata?.versatile_dice,
    thrown: p.includes('prop_thrown'),
    offhand: dualWielder ? oneHanded(item) && second(oneHanded) : isLight(item) && second(isLight),
    ability: !!char && (isFinesse(item) || !!item.martial_arts),  // Arti Marziali: il server dice se vale per quest'arma
  }
}

/** La caratteristica che il server userebbe senza scelta. */
export function bestAbility(char: ChoiceChar | undefined): 'strength' | 'dexterity' {
  const mod = (name: string) => char?.ability_scores?.find((a) => a.name === name)?.modifier ?? 0
  return mod('dexterity') > mod('strength') ? 'dexterity' : 'strength'
}

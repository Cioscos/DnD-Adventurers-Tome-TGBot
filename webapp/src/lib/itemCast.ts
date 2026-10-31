import { isAttackSpell } from '@/lib/spellType'
import { itemCharges, itemGrantedSpells, type GrantedSpell } from '@/lib/itemMagic'
import type { CharacterFull, Item } from '@/types'

export interface ResolvedItemCast {
  spell: GrantedSpell
  /** CD/attacco dell'oggetto se indicati, altrimenti quelli del personaggio (null = nessun incantatore). */
  saveDc: number | null
  attackBonus: number | null
  isAttack: boolean
  /** Abilità del TS (dall'incantesimo del personaggio con lo stesso nome), se nota. */
  saveAbility: string | null
  spent: number
  remaining: number | null
  max: number | null
}

/** Incantesimo del personaggio corrispondente (per indice SRD, poi per nome). */
function matchingSpell(char: CharacterFull, g: GrantedSpell) {
  const spells = char.spells ?? []
  const byIndex = g.srd_index
    ? spells.find((s) => (s as { srd_index?: string | null }).srd_index === g.srd_index)
    : undefined
  return byIndex ?? spells.find((s) => s.name.trim().toLowerCase() === g.name.trim().toLowerCase())
}

export function resolveItemCast(char: CharacterFull, item: Item, spellIndex: number): ResolvedItemCast | null {
  const spell = itemGrantedSpells(item)[spellIndex]
  if (!spell) return null
  const casters = char.spellcasting?.casters ?? []
  const charDc = casters.length ? Math.max(...casters.map((c) => c.save_dc)) : null
  const charAtk = casters.length ? Math.max(...casters.map((c) => c.attack_bonus)) : null
  const match = matchingSpell(char, spell)
  const isAttack = spell.attack_bonus != null || (!!match && isAttackSpell(match))
  const raw = match?.attack_save?.trim() ?? ''
  const charges = itemCharges(item)
  return {
    spell,
    saveDc: spell.save_dc ?? charDc,
    attackBonus: spell.attack_bonus ?? charAtk,
    isAttack,
    saveAbility: !isAttack && raw && raw.toUpperCase() !== 'ATK' ? raw : null,
    spent: spell.charges_cost,
    remaining: charges ? charges.current : null,
    max: charges ? charges.max : null,
  }
}

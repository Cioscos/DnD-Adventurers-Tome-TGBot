// D&D 5e multiclass ability-score prerequisites (PHB p.163). Used only for a
// NON-blocking advisory warning in the class picker — homebrew builds may ignore them.

export type AbilityKey =
  | 'strength'
  | 'dexterity'
  | 'constitution'
  | 'intelligence'
  | 'wisdom'
  | 'charisma'

/** A class requires ALL groups; within a group ANY listed ability meeting `min` satisfies it. */
export interface PrereqGroup {
  abilities: AbilityKey[]
  min: number
}

export const MULTICLASS_PREREQS: Record<string, PrereqGroup[]> = {
  barbarian: [{ abilities: ['strength'], min: 13 }],
  bard: [{ abilities: ['charisma'], min: 13 }],
  cleric: [{ abilities: ['wisdom'], min: 13 }],
  druid: [{ abilities: ['wisdom'], min: 13 }],
  fighter: [{ abilities: ['strength', 'dexterity'], min: 13 }],
  monk: [{ abilities: ['dexterity'], min: 13 }, { abilities: ['wisdom'], min: 13 }],
  paladin: [{ abilities: ['strength'], min: 13 }, { abilities: ['charisma'], min: 13 }],
  ranger: [{ abilities: ['dexterity'], min: 13 }, { abilities: ['wisdom'], min: 13 }],
  rogue: [{ abilities: ['dexterity'], min: 13 }],
  sorcerer: [{ abilities: ['charisma'], min: 13 }],
  warlock: [{ abilities: ['charisma'], min: 13 }],
  wizard: [{ abilities: ['intelligence'], min: 13 }],
}

/** Returns the prerequisite groups the character does NOT satisfy (empty = all met / unknown class). */
export function unmetPrereqGroups(
  classKey: string,
  scoreOf: (ability: AbilityKey) => number,
): PrereqGroup[] {
  const groups = MULTICLASS_PREREQS[classKey]
  if (!groups) return []
  return groups.filter((g) => !g.abilities.some((a) => scoreOf(a) >= g.min))
}

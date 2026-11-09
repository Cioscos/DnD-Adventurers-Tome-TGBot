/** Le opzioni di una scelta arrivano come slug dal server: qui diventano il nome che il giocatore legge. */
export function optionLabel(t: (k: string, o?: Record<string, unknown>) => string, key: string, option: string): string {
  const path = { skill: 'character.skills', damage_type: 'character.inventory.damage_types.dmg', ability: 'common.abilities', shield: 'character.spells.effect_shield' }[key]
  return path ? t(`${path}${key === 'damage_type' ? '_' : '.'}${option}`, { defaultValue: option }) : option
}

/** Un effetto chiede prima qualcosa: bersagli (l'aura è del lanciatore, non ne ha), scelte o l'arma da incantare. */
export function needsEffectAsk(effect: { target_kind: string; choices: unknown[]; weapon_choice?: boolean }): boolean {
  return (effect.target_kind !== 'self' && effect.target_kind !== 'aura') || effect.choices.length > 0 || !!effect.weapon_choice
}

/** Le scelte da mostrare adesso: quelle condizionate (`when`) compaiono solo dopo la scelta che le apre. */
export function visibleChoices<C extends { when?: [string, string] | null }>(choices: C[], picked: Record<string, string>): C[] {
  return choices.filter((c) => !c.when || picked[c.when[0]] === c.when[1])
}

/** Le opzioni di una scelta arrivano come slug dal server: qui diventano il nome che il giocatore legge. */
export function optionLabel(t: (k: string, o?: Record<string, unknown>) => string, key: string, option: string): string {
  if (key === 'glyph') return t(`character.spells.effect_glyph_${option}`)  // Glifo di Interdizione: rune esplosive o glifo incantesimo
  if (option === 'normal' && key === 'weapon_damage') return t('character.spells.effect_weapon_damage_normal')  // Randello Incantato 2024: il tipo dell'arma
  const path = { skill: 'character.skills', damage_type: 'character.inventory.damage_types.dmg', upcast_type: 'character.inventory.damage_types.dmg', weapon_damage: 'character.inventory.damage_types.dmg', ability: 'common.abilities', shield: 'character.spells.effect_shield' }[key]
  return path ? t(`${path}${path.endsWith('.dmg') ? '_' : '.'}${option}`, { defaultValue: option }) : option
}

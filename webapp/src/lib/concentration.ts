import type { CharacterFull } from '@/types'

type ItemSpell = { item_id: number; name: string }

/** Concentrazione da incantesimo di oggetto (non nella lista incantesimi del personaggio). */
export function itemSpellConcentration(char: Pick<CharacterFull, 'settings'>): ItemSpell | null {
  const s = (char.settings as Record<string, unknown> | undefined)?.concentration_item_spell as ItemSpell | undefined
  return s && typeof s === 'object' && s.name ? s : null
}

export function isConcentrating(char: Pick<CharacterFull, 'concentrating_spell_id' | 'settings'>): boolean {
  return !!char.concentrating_spell_id || !!itemSpellConcentration(char)
}

/** Nome dell'incantesimo in concentrazione (da lista o da oggetto), se noto. */
export function concentrationLabel(
  char: Pick<CharacterFull, 'concentrating_spell_id' | 'settings' | 'spells'>,
): string | undefined {
  if (char.concentrating_spell_id) {
    return char.spells?.find((s) => s.id === char.concentrating_spell_id)?.name
  }
  return itemSpellConcentration(char)?.name
}

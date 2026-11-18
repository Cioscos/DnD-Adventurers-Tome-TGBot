import type { DiceRollResult } from '@/types'

/** Cosa è stato tirato e con quali dadi ("Dardo di fuoco · 2d10"). I danni da incantesimo salvati prima
 *  dell'etichetta hanno solo `spell_name`. */
export function lastRollText(r: DiceRollResult & { spell_name?: string }): string {
  return [r.label ?? r.spell_name, r.notation].filter(Boolean).join(' · ')
}

import type { Spell } from '@/types'

/** Incantesimo con tiro per colpire: il d20 precede il danno (spec 2026-10-30). */
/** Punizione Divina 2024: si sceglie dopo un colpo (opzione dell'attacco), non si lancia dall'elenco. */
export const isHitOnlySpell = (spell: Pick<Spell, 'srd_index'>) => spell.srd_index === 'divine-smite'

/** Dadi tirati al lancio (foglio danni). Una punizione no: il suo danno arriva dall'opzione al colpo (al prossimo colpo nel 2014, al colpo nel 2024).
 *  Con le scelte del lancio, nemmeno se il tipo di danno non si chiede: il glifo incantesimo del Glifo non ha danni, solo le rune esplosive. */
export const rollsDamageOnCast = (spell: Pick<Spell, 'damage_dice' | 'effect'>, choices?: Record<string, string>) =>
  !!spell.damage_dice && !spell.effect?.hit_damage
  && !(choices && spell.effect?.choices?.some((c) => c.key === 'damage_type' && c.when && choices[c.when[0]] !== c.when[1]))

export const isAttackSpell = (spell: Pick<Spell, 'attack_save'>) =>
  spell.attack_save?.trim().toUpperCase() === 'ATK'

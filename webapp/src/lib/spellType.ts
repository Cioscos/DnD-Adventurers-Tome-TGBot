import type { Spell } from '@/types'

/** Incantesimo con tiro per colpire: il d20 precede il danno (spec 2026-10-30). */
/** Punizione Divina 2024: si sceglie dopo un colpo (opzione dell'attacco), non si lancia dall'elenco. */
export const isHitOnlySpell = (spell: Pick<Spell, 'srd_index'>) => spell.srd_index === 'divine-smite'

/** Dadi tirati al lancio (foglio danni). Una punizione no: il suo danno arriva dall'opzione al colpo (al prossimo colpo nel 2014, al colpo nel 2024). */
export const rollsDamageOnCast = (spell: Pick<Spell, 'damage_dice' | 'effect'>) => !!spell.damage_dice && !spell.effect?.hit_damage

export const isAttackSpell = (spell: Pick<Spell, 'attack_save'>) =>
  spell.attack_save?.trim().toUpperCase() === 'ATK'

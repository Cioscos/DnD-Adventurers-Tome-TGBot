import type { Spell } from '@/types'

/** Incantesimo con tiro per colpire: il d20 precede il danno (spec 2026-10-30). */
/** Punizione Divina 2024: si sceglie dopo un colpo (opzione dell'attacco), non si lancia dall'elenco. */
export const isHitOnlySpell = (spell: Pick<Spell, 'srd_index'>) => spell.srd_index === 'divine-smite'

export const isAttackSpell = (spell: Pick<Spell, 'attack_save'>) =>
  spell.attack_save?.trim().toUpperCase() === 'ATK'

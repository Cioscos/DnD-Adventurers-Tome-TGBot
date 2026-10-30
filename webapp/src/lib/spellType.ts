import type { Spell } from '@/types'

/** Incantesimo con tiro per colpire: il d20 precede il danno (spec 2026-10-30). */
export const isAttackSpell = (spell: Pick<Spell, 'attack_save'>) =>
  spell.attack_save?.trim().toUpperCase() === 'ATK'

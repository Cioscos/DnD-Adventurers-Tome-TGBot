import type { Spell } from '@/types'

/** Incantesimi di cura per `srd_index` (specchio di `core/rules/spell_healing.py`): per loro «Lancia» apre il tiro di cura. */
const HEALING = new Set(['cure-wounds', 'healing-word', 'mass-cure-wounds', 'mass-healing-word', 'prayer-of-healing', 'heal', 'regenerate',
  'mass-heal', 'revivify', 'raise-dead', 'goodberry'])

export const isHealingSpell = (spell: Pick<Spell, 'srd_index'> | null | undefined): boolean =>
  !!spell?.srd_index && HEALING.has(spell.srd_index)

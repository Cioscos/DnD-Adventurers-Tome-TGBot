import type { Spell } from '@/types'

/** Per un incantesimo di cura «Lancia» apre il tiro di cura: lo dice il server (`Spell.is_healing`, tabella `core/rules/spell_healing.py`). */
export const isHealingSpell = (spell: Pick<Spell, 'is_healing'> | null | undefined): boolean => !!spell?.is_healing

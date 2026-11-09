import type { SpellCopyMode } from '@/api/client'
import type { Spell } from '@/types'

/** Modi di copia che l'incantesimo ammette adesso: nel libro già, solo la copia di riserva; fuori, la copia (o la ritrascrizione
 *  se è preparato, a libro perso). Il server ricontrolla tutto e paga l'oro. */
export function bookModes(spell: Spell): SpellCopyMode[] {
  if (spell.in_spellbook) return spell.in_backup ? [] : ['backup']
  return spell.is_prepared ? ['copy', 'retranscribe'] : ['copy']
}

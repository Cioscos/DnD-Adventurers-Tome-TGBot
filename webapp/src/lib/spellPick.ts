import type { SpellEntry } from '@/lib/srd/catalog'

/** Restringe il catalogo a ciò che una scelta di incantesimi ammette: il livello massimo e, se la scelta è di un elenco di
 *  classe (trucchetto del druido), solo gli incantesimi di quell'elenco. Il server controlla il livello; l'elenco non ce l'ha. */
export function spellPickFilter(pick: { max_level: number; list?: string | null }) {
  return (e: SpellEntry): boolean =>
    e.level <= pick.max_level && (!pick.list || (e.classes ?? []).includes(pick.list))
}

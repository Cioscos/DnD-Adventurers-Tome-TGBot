import type { Ability } from '@/types'

/** Risorsa di classe senza più limite (Ira 2014 al 20): ha una ricarica ma nessun massimo.
 *  Un privilegio attivo senza contatore (Azione Scaltra) ha ricarica `none`: lo garantisce il sync. */
export function isUnlimitedFeature(a: Ability): boolean {
  return a.is_class_feature && !a.is_passive && a.max_uses == null && a.restoration_type !== 'none'
}

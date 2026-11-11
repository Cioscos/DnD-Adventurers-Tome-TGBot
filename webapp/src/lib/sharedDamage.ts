import type { TFunction } from 'i18next'
import type { CharacterFull } from '@/types'

/** Toast del danno quando un incantesimo ne gira una parte al lanciatore: i danni subiti dal bersaglio (dopo le resistenze) e quelli del lanciatore. */
export function damageTakenMessage(updated: CharacterFull, t: TFunction): string | null {
  const shared = updated.shared_damage
  if (!shared || updated.damage_taken == null) return null
  return t('character.hp.damage_taken_shared', { n: updated.damage_taken, shared: shared.amount, name: shared.caster_name })
}

/** Avviso per il bersaglio di Legame di Protezione: il danno girato al lanciatore e l'esito del suo TS di concentrazione. `null` se non c'è. */
export function sharedDamageMessage(updated: CharacterFull, t: TFunction): { text: string; ok: boolean } | null {
  const shared = updated.shared_damage
  if (!shared) return null
  const save = shared.concentration_save
  const vars = { name: shared.caster_name, amount: shared.amount, total: save?.total, dc: save?.dc }
  if (!save) return { text: t('character.hp.shared_damage', vars), ok: true }
  return { text: t(save.success ? 'character.hp.shared_damage_save_ok' : 'character.hp.shared_damage_save_fail', vars), ok: save.success }
}

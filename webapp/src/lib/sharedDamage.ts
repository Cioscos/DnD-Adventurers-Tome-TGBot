import type { TFunction } from 'i18next'
import type { CharacterFull } from '@/types'

/** Avviso per il bersaglio di Legame di Protezione: il danno girato al lanciatore e l'esito del suo TS di concentrazione. `null` se non c'è. */
export function sharedDamageMessage(updated: CharacterFull, t: TFunction): { text: string; ok: boolean } | null {
  const shared = updated.shared_damage
  if (!shared) return null
  const save = shared.concentration_save
  const vars = { name: shared.caster_name, amount: shared.amount, total: save?.total, dc: save?.dc }
  if (!save) return { text: t('character.hp.shared_damage', vars), ok: true }
  return { text: t(save.success ? 'character.hp.shared_damage_save_ok' : 'character.hp.shared_damage_save_fail', vars), ok: save.success }
}

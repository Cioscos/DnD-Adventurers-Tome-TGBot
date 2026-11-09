import type { TFunction } from 'i18next'
import type { CharacterFull } from '@/types'

/** Esito del TS automatico a 0 PF (Ira Implacabile) come testo per un avviso; `null` se il colpo non l'ha attivato. */
export function zeroHpSaveMessage(updated: CharacterFull, t: TFunction): { text: string; ok: boolean } | null {
  const save = updated.zero_hp_save
  if (!save) return null
  const name = updated.abilities.find((a) => a.feature_key === save.feature_key)?.name ?? ''
  const text = t(save.success ? 'character.hp.zero_save_ok' : 'character.hp.zero_save_fail',
    { name, total: save.total, dc: save.dc, hp: save.hp })
  return { text, ok: save.success }
}

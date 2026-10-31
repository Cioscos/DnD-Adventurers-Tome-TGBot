import type { TFunction } from 'i18next'
import type { ConditionEffect } from '@/types'

const K = 'character.conditions.effect'

/** Scadenza leggibile di un effetto ("" se non ne ha). Con ancora: turni owner/source; senza: round manuali. */
export function formatExpiry(effect: ConditionEffect, t: TFunction): string {
  const { expiry_anchor: anchor, expiry_edge: edge, expiry_count: n } = effect
  const parts: string[] = []
  if (n != null && n > 0) {
    if (anchor && edge) {
      const base = `${K}.until_${edge}_${anchor}`
      const name = effect.source_name || t(`${K}.source_unknown`)
      parts.push(t(n === 1 ? `${base}_next` : `${base}_nth`, { n, name }))
    } else {
      parts.push(t(`${K}.rounds`, { count: n }))
    }
  }
  if (effect.ends_with_concentration && effect.source_name) {
    parts.push(t(`${K}.while_concentrating`, { name: effect.source_name }))
  }
  return parts.join(' · ')
}

/** TS ripetuto ("TS COS CD 13 alla fine del tuo turno"), null se assente. */
export function formatSave(effect: ConditionEffect, t: TFunction): string | null {
  if (!effect.save_ability || effect.save_dc == null) return null
  return t(`${K}.save_${effect.save_edge ?? 'any'}`, {
    ability: t(`character.ability.${effect.save_ability}_short`),
    dc: effect.save_dc,
  })
}

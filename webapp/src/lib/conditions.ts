import type { TFunction } from 'i18next'
import {
  GiBlindfold, GiHearts, GiSoundOff, GiGhost, GiManacles, GiCloudRing,
  GiInvisible, GiLightningTrio, GiMountains, GiPoisonBottle, GiFalling,
  GiHandcuffs, GiSparkles, GiNightSleep, GiFlame,
} from 'react-icons/gi'
import type { IconType } from 'react-icons'

/**
 * Icon lookup for the 14 standard 5e conditions plus exhaustion.
 * Used by the hero section (icon-only chips) and the /conditions page (icon+label).
 */
export const CONDITION_ICONS: Record<string, IconType> = {
  blinded:       GiBlindfold,
  charmed:       GiHearts,
  deafened:      GiSoundOff,
  frightened:    GiGhost,
  grappled:      GiManacles,
  incapacitated: GiCloudRing,
  invisible:     GiInvisible,
  paralyzed:     GiLightningTrio,
  petrified:     GiMountains,
  poisoned:      GiPoisonBottle,
  prone:         GiFalling,
  restrained:    GiHandcuffs,
  stunned:       GiSparkles,
  unconscious:   GiNightSleep,
  exhaustion:    GiFlame,
}

/** Condizioni `custom:<nome>` che il catalogo dei privilegi imposta su altri: hanno l'etichetta in `target_effect.custom`
 *  (specchio di `CUSTOM_CONDITION_LABELS` in `core/data/labels.py`). Quelle scritte dal giocatore si mostrano col suo nome. */
const CATALOG_CUSTOM = ['turned', 'thoughts_read', 'nature_ward', 'sap', 'slow', 'goaded', 'protection', 'eldritch_strike']

/** Nome di una condizione per slug, anche `custom:<nome>`: mai la chiave grezza. */
export function conditionLabel(slug: string, t: TFunction): string {
  if (slug.startsWith('custom:')) {
    const name = slug.slice('custom:'.length)
    return CATALOG_CUSTOM.includes(name) ? t(`character.target_effect.custom.${name}`, { defaultValue: name }) : name
  }
  return t(`character.conditions.${slug}`, { defaultValue: slug })
}

/**
 * Localise a condition label for display in a pill / list.
 *
 * Exhaustion renders with its level (e.g. "Spossatezza (livello 3)") when
 * val is a positive number; all other conditions render by slug.
 */
export function formatCondition(
  key: string,
  val: unknown,
  t: TFunction,
  edition?: string,
): string {
  if (key === 'exhaustion' && typeof val === 'number' && val > 0) {
    return t('character.conditions.exhaustion', { level: val, context: edition })
  }
  return key.startsWith('custom:') ? conditionLabel(key, t) : t(`character.conditions.${key}`)
}

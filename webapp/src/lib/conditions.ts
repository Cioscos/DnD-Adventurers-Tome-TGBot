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
): string {
  if (key === 'exhaustion' && typeof val === 'number' && val > 0) {
    return t('character.conditions.exhaustion', { level: val })
  }
  return t(`character.conditions.${key}`)
}

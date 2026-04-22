import type { TFunction } from 'i18next'
import {
  EyeOff, Heart, VolumeX, Ghost, Link2, Cloud, Eye, Zap, Mountain,
  FlaskConical, ArrowDown, Lock, Sparkle, Moon, Flame,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

/**
 * Icon lookup for the 14 standard 5e conditions plus exhaustion.
 * Used by the hero section (icon-only chips) and the /conditions page (icon+label).
 */
export const CONDITION_ICONS: Record<string, LucideIcon> = {
  blinded:       EyeOff,
  charmed:       Heart,
  deafened:      VolumeX,
  frightened:    Ghost,
  grappled:      Link2,
  incapacitated: Cloud,
  invisible:     Eye,
  paralyzed:     Zap,
  petrified:     Mountain,
  poisoned:      FlaskConical,
  prone:         ArrowDown,
  restrained:    Lock,
  stunned:       Sparkle,
  unconscious:   Moon,
  exhaustion:    Flame,
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

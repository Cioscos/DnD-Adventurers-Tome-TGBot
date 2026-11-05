import { localized, type Lang, type MonsterEntry } from '@/lib/srd/catalog'
import type { CompanionAction, CompanionKind, CompanionStatblock } from '@/types'

export const KINDS: CompanionKind[] = ['familiar', 'companion', 'mount', 'summon', 'wild_shape']

// Find Familiar (PHB 2014): the SRD forms a familiar may take.
const FAMILIAR_FORMS = new Set([
  'bat', 'cat', 'crab', 'frog', 'hawk', 'lizard', 'octopus', 'owl', 'poisonous-snake', 'quipper',
  'rat', 'raven', 'sea-horse', 'spider', 'weasel',
])

type Rule = Pick<MonsterEntry, 'index' | 'type' | 'challenge_rating' | 'speed'>

// Forma Selvatica Elementale (Circolo della Luna 2014, dal 10°): i quattro elementali, senza limiti di GS (mirror di `core/rules/forms.py`).
const ELEMENTALS = new Set(['air-elemental', 'earth-elemental', 'fire-elemental', 'water-elemental'])

/** i18n key of the advisory warning, or null when the form is allowed. */
export function familiarWarning(entry: Pick<MonsterEntry, 'index'>): string | null {
  return FAMILIAR_FORMS.has(entry.index) ? null : 'character.extras.warn.familiar_form'
}

/** Highest CR a druid can assume: mirrors `core/rules/forms.py` (the server blocks what breaks it).
 * 2014 Moon: 1 up to level 5, then level/3; 2024 Moon: level/3 from level 3. */
export function wildShapeMaxCr(druidLevel: number, isMoon: boolean, edition: string = '2014'): number {
  if (isMoon && edition !== '2024') return druidLevel < 6 ? 1 : Math.floor(druidLevel / 3)
  if (isMoon && druidLevel >= 3) return Math.floor(druidLevel / 3)
  return druidLevel < 4 ? 0.25 : druidLevel < 8 ? 0.5 : 1
}

/** i18n key of the first broken Wild Shape limit, or null. Advisory: the server asks to confirm on activation. */
export function wildShapeWarning(entry: Rule, druidLevel: number, isMoon: boolean, edition: string = '2014'): string | null {
  if (edition !== '2024' && isMoon && druidLevel >= 10 && ELEMENTALS.has(entry.index)) return null // Forma Selvatica Elementale
  if (entry.type !== 'beast') return 'character.extras.warn.not_beast'
  if (entry.challenge_rating > wildShapeMaxCr(druidLevel, isMoon, edition)) return 'character.extras.warn.cr'
  if ((entry.speed.fly_ft ?? 0) > 0 && druidLevel < 8) return 'character.extras.warn.fly'
  // 2024 limits only CR and flying: swimming is free
  if (edition !== '2024' && (entry.speed.swim_ft ?? 0) > 0 && druidLevel < 4) return 'character.extras.warn.swim'
  return null
}

/** Formats a CR the way the books do (1/8, 1/4, 1/2, N). */
export function formatCr(cr: number): string {
  return cr === 0.125 ? '1/8' : cr === 0.25 ? '1/4' : cr === 0.5 ? '1/2' : String(cr)
}

const loc = (f: Parameters<typeof localized>[0], lang: Lang) => localized(f, lang)

const nonEmpty = (o?: Record<string, number>) => !!o && Object.keys(o).length > 0

/** Catalogue monster -> companion statblock; flat damage ("1") becomes "1d1" for the server's NdX rule. */
export function monsterToStatblock(e: MonsterEntry, lang: Lang): CompanionStatblock {
  const convert = (name: MonsterEntry['traits'][number]['name'], desc: MonsterEntry['traits'][number]['desc']) => {
    const n = loc(name, lang)
    const d = loc(desc, lang)
    return { name: n.text, desc: d.text, ...(n.fallback || d.fallback ? { en: true } : {}) }
  }
  const actions: CompanionAction[] = e.actions.map((a) => ({
    ...convert(a.name, a.desc),
    attack_bonus: a.attack_bonus,
    damage_dice: a.damage_dice && /^\d+$/.test(a.damage_dice) ? `${a.damage_dice}d1` : a.damage_dice,
    damage_type: a.damage_type,
  }))
  return {
    size: e.size, type: e.type, speed: e.speed, abilities: e.abilities, challenge_rating: e.challenge_rating,
    // competenze della creatura (bonus totali): il server le dà al druido in Forma Selvatica
    ...(nonEmpty(e.skills) ? { skills: e.skills } : {}),
    ...(nonEmpty(e.saves) ? { saves: e.saves } : {}),
    traits: e.traits.map((tr) => convert(tr.name, tr.desc)),
    actions,
  }
}

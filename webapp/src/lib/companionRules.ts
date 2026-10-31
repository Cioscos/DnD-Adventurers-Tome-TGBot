import { localized, type Lang, type MonsterEntry } from '@/lib/srd/catalog'
import type { CompanionAction, CompanionKind, CompanionStatblock } from '@/types'

export const KINDS: CompanionKind[] = ['familiar', 'companion', 'mount', 'summon', 'wild_shape']

// Find Familiar (PHB 2014): the SRD forms a familiar may take.
const FAMILIAR_FORMS = new Set([
  'bat', 'cat', 'crab', 'frog', 'hawk', 'lizard', 'octopus', 'owl', 'poisonous-snake', 'quipper',
  'rat', 'raven', 'sea-horse', 'spider', 'weasel',
])

type Rule = Pick<MonsterEntry, 'index' | 'type' | 'challenge_rating' | 'speed'>

/** i18n key of the advisory warning, or null when the form is allowed. */
export function familiarWarning(entry: Pick<MonsterEntry, 'index'>): string | null {
  return FAMILIAR_FORMS.has(entry.index) ? null : 'character.extras.warn.familiar_form'
}

/** Highest CR a druid can assume (Moon circle: 1 at level 2, level/3 from 6). */
export function wildShapeMaxCr(druidLevel: number, isMoon: boolean): number {
  if (isMoon) return druidLevel < 6 ? 1 : Math.floor(druidLevel / 3)
  return druidLevel < 4 ? 0.25 : druidLevel < 8 ? 0.5 : 1
}

/** i18n key of the first broken Wild Shape limit, or null. Advisory only. */
export function wildShapeWarning(entry: Rule, druidLevel: number, isMoon: boolean): string | null {
  if (entry.type !== 'beast') return 'character.extras.warn.not_beast'
  if (entry.challenge_rating > wildShapeMaxCr(druidLevel, isMoon)) return 'character.extras.warn.cr'
  if ((entry.speed.fly_ft ?? 0) > 0 && druidLevel < 8) return 'character.extras.warn.fly'
  if ((entry.speed.swim_ft ?? 0) > 0 && druidLevel < 4) return 'character.extras.warn.swim'
  return null
}

/** Formats a CR the way the books do (1/8, 1/4, 1/2, N). */
export function formatCr(cr: number): string {
  return cr === 0.125 ? '1/8' : cr === 0.25 ? '1/4' : cr === 0.5 ? '1/2' : String(cr)
}

const loc = (f: Parameters<typeof localized>[0], lang: Lang) => localized(f, lang)

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
    traits: e.traits.map((tr) => convert(tr.name, tr.desc)),
    actions,
  }
}

import manifest from '@/data/silhouette-manifest.json'
import type { CharacterFull } from '@/types'

const MANIFEST_SET: ReadonlySet<string> = new Set(manifest as string[])

const CANONICAL_CLASSES: ReadonlySet<string> = new Set([
  'barbarian', 'bard', 'cleric', 'druid', 'fighter', 'monk',
  'paladin', 'ranger', 'rogue', 'sorcerer', 'warlock', 'wizard',
])

const RACE_SLUG_MAP: Record<string, string> = {
  human: 'human', umano: 'human', umana: 'human',
  elf: 'elf', elfo: 'elf', elfa: 'elf',
  dwarf: 'dwarf', nano: 'dwarf', nana: 'dwarf',
  halfling: 'halfling', mezzuomo: 'halfling',
  half_elf: 'half_elf', mezzelfo: 'half_elf', mezzelfa: 'half_elf', 'half-elf': 'half_elf',
  half_orc: 'half_orc', mezzorco: 'half_orc', 'half-orc': 'half_orc',
  gnome: 'gnome', gnomo: 'gnome', gnoma: 'gnome',
  tiefling: 'tiefling',
  dragonborn: 'dragonborn', dracoide: 'dragonborn',
}

const GENDER_SLUG_MAP: Record<string, string> = {
  m: 'male', male: 'male', maschio: 'male', maschile: 'male',
  f: 'female', female: 'female', femmina: 'female', femminile: 'female',
}

function pickPrimaryCanonicalClass(char: CharacterFull): string | null {
  const canonical = (char.classes ?? []).filter((c) =>
    CANONICAL_CLASSES.has(c.class_name),
  )
  if (canonical.length === 0) return null
  // Highest level wins; tie-break alphabetic on class_name for determinism.
  canonical.sort((a, b) => {
    if (b.level !== a.level) return b.level - a.level
    return a.class_name.localeCompare(b.class_name)
  })
  return canonical[0].class_name
}

function slugFrom(map: Record<string, string>, raw: string | null | undefined): string | null {
  if (!raw) return null
  const key = raw.trim().toLowerCase()
  return map[key] ?? null
}

/**
 * Resolve a class+race+gender silhouette image URL for a character.
 *
 * Falls back through: class_race_gender → class_race → class_gender → class.
 * Returns null when no canonical class is present or no candidate matches.
 * Caller should render the existing SVG silhouette when this returns null.
 */
export function silhouetteUrl(char: CharacterFull): string | null {
  const classSlug = pickPrimaryCanonicalClass(char)
  if (!classSlug) return null

  const raceSlug = slugFrom(RACE_SLUG_MAP, char.race)
  const genderSlug = slugFrom(GENDER_SLUG_MAP, char.gender)

  const candidates: string[] = []
  if (raceSlug && genderSlug) candidates.push(`${classSlug}_${raceSlug}_${genderSlug}.png`)
  if (raceSlug) candidates.push(`${classSlug}_${raceSlug}.png`)
  if (genderSlug) candidates.push(`${classSlug}_${genderSlug}.png`)
  candidates.push(`${classSlug}.png`)

  for (const file of candidates) {
    if (MANIFEST_SET.has(file)) {
      return `${import.meta.env.BASE_URL}silhouettes/${file}`
    }
  }
  return null
}

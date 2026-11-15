import { localized, type BaseEntry, type Lang, type LocalizedField } from '@/lib/srd/catalog'

export interface RaceTrait { index: string; name: LocalizedField; desc: LocalizedField }
export interface SubraceEntry {
  index: string
  name: LocalizedField
  ability_bonuses?: Record<string, number>
  senses?: { type: string; range_ft: number }[]
  speed_ft?: number
  traits?: RaceTrait[]
  languages?: string[]
  roll_notes?: Record<string, LocalizedField>
}
export interface RaceEntry extends BaseEntry {
  speed_ft: number
  ability_bonuses: Record<string, number>
  senses: { type: string; range_ft: number }[]
  languages: string[]
  traits: RaceTrait[]
  subraces: SubraceEntry[]
  roll_notes: Record<string, LocalizedField>
}

export interface SpeciesPayload {
  name: string
  speed_ft: number | null
  senses: { type: string; range_ft: number }[]
  languages: string[]
  ability_bonuses: Record<string, number>
  roll_notes: Record<string, string>
  traits: { name: string; description: string }[]
}

// Curated catalogue note id -> roll-note key (what the character sheet reads).
const NOTE_KEY: Record<string, string> = {
  poison_save: 'save.constitution',
  charm_save: 'save.wisdom',
  frightened_save: 'save.wisdom',
}

const LANGS: Record<string, LocalizedField> = {
  common: { en: 'Common', it: 'Comune' }, dwarvish: { en: 'Dwarvish', it: 'Nanico' },
  elvish: { en: 'Elvish', it: 'Elfico' }, gnomish: { en: 'Gnomish', it: 'Gnomesco' },
  halfling: { en: 'Halfling', it: 'Halfling' }, orc: { en: 'Orc', it: 'Orchesco' },
  draconic: { en: 'Draconic', it: 'Draconico' }, infernal: { en: 'Infernal', it: 'Infernale' },
}

export const NOTE_MAX = 120

/** Merge race + optional subrace into the payload accepted by POST /characters. */
export function buildSpecies(race: RaceEntry, sub: SubraceEntry | null, lang: Lang): SpeciesPayload {
  const bonuses = { ...race.ability_bonuses }
  for (const [k, v] of Object.entries(sub?.ability_bonuses ?? {})) bonuses[k] = (bonuses[k] ?? 0) + v
  const senses = new Map<string, number>()
  for (const s of [...race.senses, ...(sub?.senses ?? [])]) {
    senses.set(s.type, Math.max(senses.get(s.type) ?? 0, s.range_ft))
  }
  const notes: Record<string, string> = {}
  for (const [id, f] of Object.entries({ ...race.roll_notes, ...(sub?.roll_notes ?? {}) })) {
    const key = NOTE_KEY[id]
    if (key) notes[key] = [notes[key], localized(f, lang).text].filter(Boolean).join(' ').slice(0, NOTE_MAX)
  }
  const langs = [...new Set([...race.languages, ...(sub?.languages ?? [])])]
  return {
    name: localized(sub?.name ?? race.name, lang).text,
    speed_ft: sub?.speed_ft ?? race.speed_ft,
    senses: [...senses].map(([type, range_ft]) => ({ type, range_ft })),
    languages: langs.map((l) => (LANGS[l] ? localized(LANGS[l], lang).text : l)),
    ability_bonuses: bonuses,
    roll_notes: notes,
    traits: [...race.traits, ...(sub?.traits ?? [])].map((tr) => ({
      name: localized(tr.name, lang).text,
      description: localized(tr.desc, lang).text,
    })),
  }
}

// Mirror of core/data/skills.py SKILLS keys (the sheet's Skills page uses the same slugs).
export const SKILL_KEYS = [
  'acrobatics', 'animal_handling', 'arcana', 'athletics', 'deception', 'history', 'insight',
  'intimidation', 'investigation', 'medicine', 'nature', 'perception', 'performance', 'persuasion',
  'religion', 'sleight_of_hand', 'stealth', 'survival',
]

/** Catalogue skill names -> backend slugs; unknown ones are dropped (an unknown slug would 422 the whole create). */
export function backgroundSkills(skills: string[] | undefined): string[] {
  return (skills ?? []).map((k) => k.replace(/-/g, '_')).filter((k) => SKILL_KEYS.includes(k))
}

/** Fixed languages of a catalogue background (none in the SRD: "two of your choice"), localised. */
export function backgroundLanguages(langs: string[] | undefined, lang: Lang): string[] {
  return (langs ?? []).map((l) => (LANGS[l] ? localized(LANGS[l], lang).text : l))
}

// --- Cataloghi 2024 (species-2024.json / backgrounds-2024.json, specchio di core/data) ---

type Bilingual = { it: string; en: string }
export interface Species2024Choice {
  key: string
  label: Bilingual
  from_level: number
  options: { key: string; label: Bilingual }[]
}
export interface Species2024Entry extends BaseEntry {
  key: string
  size: string[]
  speed_ft: number
  choices: Species2024Choice[]
  traits: { key: string; name: Bilingual; summary: Bilingual }[]
}
export interface Background2024Entry extends BaseEntry {
  key: string
  abilities: string[]
  origin_feat: string
  skills: string[]
  /** Stringa = strumento fisso; lista = da scegliere. */
  tool: string | string[]
  equipment: string
  feat_list: string | null
}

/** Scelte che il server richiede alla creazione (core/data/species_2024.py `required_choices`) ancora senza un'opzione valida. */
export function speciesChoicesMissing(entry: Species2024Entry, options: Record<string, string>): string[] {
  return entry.choices
    .filter((c) => c.from_level <= 1 && !c.options.some((o) => o.key === options[c.key]))
    .map((c) => c.key)
}

export interface Background2024Choice {
  entry: Background2024Entry
  increases: Record<string, number>
  tool: string | null
  equipment: 'pack' | 'gold'
}

/** +2/+1 o +1/+1/+1 fra le tre caratteristiche del background, e lo strumento se è a scelta (come il router). */
export function increasesValid(increases: Record<string, number>): boolean {
  const vals = Object.values(increases).filter((v) => v > 0).sort().join(',')
  return vals === '1,2' || vals === '1,1,1'
}

export function background24Valid(c: Background2024Choice | null): boolean {
  if (!c) return true
  return increasesValid(c.increases) && (!Array.isArray(c.entry.tool) || c.entry.tool.includes(c.tool ?? ''))
}

export function background24Payload(c: Background2024Choice) {
  const increases = Object.fromEntries(Object.entries(c.increases).filter(([, v]) => v > 0))
  return { key: c.entry.key, increases, ...(c.tool ? { tool: c.tool } : {}), equipment: c.equipment }
}

/** Extra POST /characters fields: scores are always sent (what you see is what you get) unless the step was skipped. */
export function creationExtras(o: {
  scores: Record<string, number>
  skipped: boolean
  species: SpeciesPayload | null
  skills: string[]
}) {
  return {
    ...(o.skipped ? {} : { ability_scores: o.scores }),
    ...(o.species ? { species: o.species } : {}),
    ...(o.skills.length ? { skills: Object.fromEntries(o.skills.map((k) => [k, true])) } : {}),
  }
}

import { localized, type BaseEntry, type Lang, type LocalizedField } from '@/lib/srd/catalog'

export interface RaceTrait { index: string; name: LocalizedField; desc: LocalizedField }
/** Competenze e resistenze fisse della razza (chiavi di abilità, core.rules.weapons, core.data.tools, tipi di danno). */
interface RaceGrants { skills?: string[]; weapons?: string[]; tools?: string[]; resistances?: string[] }
export interface SubraceEntry extends RaceGrants {
  index: string
  name: LocalizedField
  ability_bonuses?: Record<string, number>
  senses?: { type: string; range_ft: number }[]
  speed_ft?: number
  traits?: RaceTrait[]
  languages?: string[]
  roll_notes?: Record<string, LocalizedField>
}
export interface RaceEntry extends BaseEntry, RaceGrants {
  speed_ft: number
  ability_bonuses: Record<string, number>
  /** Quante altre caratteristiche a scelta prendono +1 (Mezzelfo). */
  ability_choices?: number
  /** Abilità e lingue a scelta (Mezzelfo: Versatilità nelle Abilità e linguaggio extra, 2014 pag. 39). */
  skill_choices?: number
  language_choices?: number
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
  weapons: string[]
  tools: string[]
  resistances: string[]
  /** creationExtras le unisce alle abilità d'origine (il server rifiuta i doppioni con la classe); nel campo species restano
   *  quelle che vengono solo dalla razza: il passaggio a una specie 2024 le toglie. */
  skills: string[]
}

// Curated catalogue note id -> roll-note keys (what the character sheet reads).
const NOTE_KEY: Record<string, string[]> = {
  poison_save: ['save.constitution'],
  charm_save: ['save.wisdom'],
  frightened_save: ['save.wisdom'],
  magic_save: ['save.intelligence', 'save.wisdom', 'save.charisma'],
}

const LANGS: Record<string, LocalizedField> = {
  common: { en: 'Common', it: 'Comune' }, dwarvish: { en: 'Dwarvish', it: 'Nanico' },
  elvish: { en: 'Elvish', it: 'Elfico' }, gnomish: { en: 'Gnomish', it: 'Gnomesco' },
  halfling: { en: 'Halfling', it: 'Halfling' }, orc: { en: 'Orc', it: 'Orchesco' },
  draconic: { en: 'Draconic', it: 'Draconico' }, infernal: { en: 'Infernal', it: 'Infernale' },
  giant: { en: 'Giant', it: 'Gigante' }, goblin: { en: 'Goblin', it: 'Goblin' },
  abyssal: { en: 'Abyssal', it: 'Abissale' }, celestial: { en: 'Celestial', it: 'Celestiale' },
  primordial: { en: 'Primordial', it: 'Primordiale' }, deep_speech: { en: 'Deep Speech', it: 'Profondo' },
  sylvan: { en: 'Sylvan', it: 'Silvano' }, undercommon: { en: 'Undercommon', it: 'Sottocomune' },
}
export const LANGUAGE_KEYS = Object.keys(LANGS)
export const languageName = (key: string, lang: Lang): string => (LANGS[key] ? localized(LANGS[key], lang).text : key)

/** Razza 2014 scelta nella creazione. `sub`: null = «altra sottorazza», da completare a mano; undefined = non ancora scelta (2014 pag. 17:
 *  dove la razza ne ha, è obbligatoria). Mezzelfo (pag. 39): `picks` le caratteristiche a scelta che prendono +1, `skills` le abilità,
 *  `languages` le lingue (chiavi). */
export interface SpeciesChoice {
  race: RaceEntry | null
  sub: SubraceEntry | null | undefined
  picks?: string[]
  skills?: string[]
  languages?: string[]
}

/** Una scelta che la razza richiede manca ancora: Avanti resta bloccato. */
export const raceChoicesMissing = ({ race, sub, picks, skills, languages }: SpeciesChoice): boolean =>
  !!race && ((race.subraces.length > 0 && sub === undefined)
    || (picks?.length ?? 0) !== (race.ability_choices ?? 0)
    || (skills?.length ?? 0) !== (race.skill_choices ?? 0)
    || (languages?.length ?? 0) !== (race.language_choices ?? 0))

export const NOTE_MAX = 120

/** Aumenti di razza, sottorazza e caratteristiche scelte (`picks`: +1 ciascuna). */
export function raceBonuses(race: RaceEntry | null, sub: SubraceEntry | null | undefined, picks: string[] = []): Record<string, number> {
  const bonuses: Record<string, number> = { ...race?.ability_bonuses }
  for (const [k, v] of Object.entries(sub?.ability_bonuses ?? {})) bonuses[k] = (bonuses[k] ?? 0) + v
  for (const k of picks) bonuses[k] = (bonuses[k] ?? 0) + 1
  return bonuses
}

/** Merge race + optional subrace into the payload accepted by POST /characters. */
export function buildSpecies(race: RaceEntry, sub: SubraceEntry | null, lang: Lang, chosen: Pick<SpeciesChoice, 'picks' | 'skills' | 'languages'> = {}): SpeciesPayload {
  const senses = new Map<string, number>()
  for (const s of [...race.senses, ...(sub?.senses ?? [])]) {
    senses.set(s.type, Math.max(senses.get(s.type) ?? 0, s.range_ft))
  }
  const notes: Record<string, string> = {}
  for (const [id, f] of Object.entries({ ...race.roll_notes, ...(sub?.roll_notes ?? {}) })) {
    for (const key of NOTE_KEY[id] ?? []) {
      notes[key] = [notes[key], localized(f, lang).text].filter(Boolean).join(' ').slice(0, NOTE_MAX)
    }
  }
  const langs = [...new Set([...race.languages, ...(sub?.languages ?? []), ...(chosen.languages ?? [])])]
  const grants = (k: keyof RaceGrants) => [...new Set([...(race[k] ?? []), ...(sub?.[k] ?? [])])]
  return {
    name: localized(sub?.name ?? race.name, lang).text,
    speed_ft: sub?.speed_ft ?? race.speed_ft,
    senses: [...senses].map(([type, range_ft]) => ({ type, range_ft })),
    languages: langs.map((l) => languageName(l, lang)),
    ability_bonuses: raceBonuses(race, sub, chosen.picks),
    roll_notes: notes,
    traits: [...race.traits, ...(sub?.traits ?? [])].map((tr) => ({
      name: localized(tr.name, lang).text,
      description: localized(tr.desc, lang).text,
    })),
    weapons: grants('weapons'),
    tools: grants('tools'),
    resistances: grants('resistances'),
    skills: [...new Set([...grants('skills'), ...(chosen.skills ?? [])])],
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
  return (langs ?? []).map((l) => languageName(l, lang))
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
  const raceSkills = (o.species?.skills ?? []).filter((k) => !o.skills.includes(k))
  const skills = [...o.skills, ...raceSkills]
  return {
    ...(o.skipped ? {} : { ability_scores: o.scores }),
    ...(o.species ? { species: { ...o.species, skills: raceSkills } } : {}),
    ...(skills.length ? { skills: Object.fromEntries(skills.map((k) => [k, true])) } : {}),
  }
}

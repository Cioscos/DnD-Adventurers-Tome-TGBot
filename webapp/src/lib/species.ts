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

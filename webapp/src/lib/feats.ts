import feats2024 from '@/data/feats2024.json'
import { CANONICAL_CLASSES } from '@/lib/silhouette'
import type { CharacterFull } from '@/types'

export const ABILITY_KEYS = [
  'strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma',
] as const

/** Talenti selezionabili (specchio di core/data/feats.py); testi in `character.level_choice.feats.<key>`. */
export const FEAT_OPTIONS: { key: string; abilities?: readonly string[] }[] = [
  { key: 'grappler' },
  { key: 'alert' },
  { key: 'tough' },
  { key: 'mobile' },
  { key: 'observant', abilities: ['intelligence', 'wisdom'] },
  { key: 'resilient', abilities: ABILITY_KEYS },
  { key: 'war_caster' },
  { key: 'lucky' },
]

export interface Feat2024 {
  key: string
  name: { it: string; en: string }
  summary: { it: string; en: string }
  category: 'general' | 'epic_boon' | 'origin' | 'fighting_style'
  abilities: string[] | null
  min_level: number
  max_score: number
  prereq_abilities: { any_of: string[]; min: number } | null
  needs_spellcasting: boolean
  /** Si prende più volte (Abile, Iniziato alla magia): ogni presa è una riga a sé. */
  repeatable: boolean
  /** Scelte del talento da completare dopo averlo preso (`picks`, `tools`, `instruments`, `list`...). */
  needs: string[]
  /** Addestramento richiesto (`light`, `medium`, `heavy`, `shields`). */
  prereq_armor: string | null
  /** Stile di Combattimento come talento: serve il privilegio Stile di Combattimento. */
  needs_fighting_style: boolean
}

/** Testi di `general_proficiencies.armor` che valgono ogni addestramento (specchio di `core/rules/proficiencies.py`). */
const ARMOR_ALIASES: Record<string, string[]> = {
  light: ['light', 'armature leggere', 'light armor'],
  medium: ['medium', 'armature medie', 'medium armor'],
  heavy: ['heavy', 'armature pesanti', 'heavy armor'],
  shields: ['shields', 'scudi', 'shield'],
}

/** Come `armor_trained` del server: con una classe personalizzata, o mai seminato e senza competenze, il prerequisito passa. */
function armorTrained(char: CharacterFull, kind: string): boolean {
  if (char.classes.some((c) => !CANONICAL_CLASSES.has(c.class_name))) return true
  const raw = char.general_proficiencies ?? {}
  const p = Array.isArray(raw) ? { other: raw } as Partial<Record<'armor' | 'weapons' | 'tools' | 'other', string[]>> : raw
  const armorOrOther = [...(p.armor ?? []), ...(p.other ?? [])]
  if (!armorOrOther.length && !char.settings?.proficiencies_seeded) return true
  const have = armorOrOther.map((x) => x.trim().toLowerCase())
  return (ARMOR_ALIASES[kind] ?? [kind]).some((alias) => have.includes(alias))
}

/** Livello di classe dal quale le classi 2024 hanno Stile di Combattimento (specchio del catalogo). */
const STYLE_LEVEL: Record<string, number> = { fighter: 1, paladin: 2, ranger: 2 }
const STYLE_PREFIX = 'feat.2024_fs_'

/** Stili già presi: dalle classi e come talento (`feat.2024_fs_<stile>`). */
function stylesTaken(char: CharacterFull): Set<string> {
  const fromClasses = char.classes.flatMap((c) => ((c.options ?? {}) as Record<string, string[]>).fighting_style ?? [])
  const fromFeats = (char.abilities ?? []).map((a) => a.feature_key ?? '').filter((k) => k.startsWith(STYLE_PREFIX))
    .map((k) => k.slice(STYLE_PREFIX.length))
  return new Set([...fromClasses, ...fromFeats])
}

function styleOk(f: Feat2024, char: CharacterFull): boolean {
  if (!f.needs_fighting_style) return true
  const hasFeature = char.classes.some((c) => c.level >= (STYLE_LEVEL[c.class_name] ?? Infinity))
  return hasFeature && !stylesTaken(char).has(f.key.slice('2024_fs_'.length))
}

/** Talenti d'Origine, generali e Doni Epici 2024 (specchio di core/data/feats_2024.py, rigenerato da scripts/export_feats_2024.py). */
export const FEATS_2024 = feats2024 as Feat2024[]

/** Vero se il personaggio soddisfa i prerequisiti verificabili (livello, caratteristica, incantesimi).
 *  `manual` («Aggiungi talento») ignora il livello minimo, salvo per i Doni Epici (come il server). */
export function meetsPrerequisites(f: Feat2024, char: CharacterFull, opts: { manual?: boolean } = {}): boolean {
  const score = (n: string) => char.ability_scores.find((s) => s.name === n)?.value ?? 10
  const levelOk = (opts.manual && f.category !== 'epic_boon') || (char.total_level ?? 0) >= f.min_level
  return levelOk
    && (!f.prereq_abilities || f.prereq_abilities.any_of.some((a) => score(a) >= f.prereq_abilities!.min))
    && (!f.needs_spellcasting || char.classes.some((c) => !!c.spellcasting_ability))
    && (!f.prereq_armor || armorTrained(char, f.prereq_armor))
    && styleOk(f, char)
}

/** Una voce delle liste dei talenti. I talenti 2014 non hanno `name`/`summary`: i testi stanno nei locale
 *  (`character.level_choice.feats.<key>`). */
export interface FeatItem {
  key: string
  name?: string
  summary?: string
  abilities?: readonly string[]
  cap: number
  unmet: boolean
  repeatable: boolean
  needs: string[]
  category: Feat2024['category']
}

export type FeatListMode = 'level' | 'boon' | 'manual' | 'creation'

/** I talenti offerti in un punto dell'app: scelta di livello, Dono Epico, «Aggiungi talento» o creazione 2024.
 *  `char` nullo solo nella creazione (i talenti d'Origine non hanno prerequisiti). */
export function featsFor(char: CharacterFull | null, edition: '2014' | '2024', mode: FeatListMode, lang: 'it' | 'en'): FeatItem[] {
  if (edition === '2014' && mode !== 'boon') {
    return FEAT_OPTIONS.map((f) => ({
      key: f.key, abilities: f.abilities, cap: 20, unmet: false, repeatable: false, needs: [], category: 'general' as const,
    }))
  }
  const level = char?.total_level ?? 0
  const wanted = (f: Feat2024) => mode === 'creation' ? f.category === 'origin'
    : mode === 'boon' ? f.category === 'epic_boon'
      : mode === 'level' ? f.category !== 'epic_boon'
        : f.category !== 'epic_boon' || level >= f.min_level
  return FEATS_2024.filter(wanted).map((f) => ({
    key: f.key, name: f.name[lang], summary: f.summary[lang], abilities: f.abilities ?? undefined, cap: f.max_score,
    unmet: char ? !meetsPrerequisites(f, char, { manual: mode === 'manual' }) : false,
    repeatable: f.repeatable, needs: f.needs, category: f.category,
  }))
}

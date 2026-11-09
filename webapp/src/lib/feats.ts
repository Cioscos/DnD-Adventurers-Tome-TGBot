import feats2024 from '@/data/feats2024.json'
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
  category: 'general' | 'epic_boon'
  abilities: string[] | null
  min_level: number
  max_score: number
  prereq_abilities: { any_of: string[]; min: number } | null
  needs_spellcasting: boolean
}

/** Talenti generali e Doni Epici 2024 (specchio di core/data/feats_2024.py, rigenerato da scripts/export_feats_2024.py). */
export const FEATS_2024 = feats2024 as Feat2024[]

/** Vero se il personaggio soddisfa i prerequisiti verificabili (livello, caratteristica, incantesimi). */
export function meetsPrerequisites(f: Feat2024, char: CharacterFull): boolean {
  const score = (n: string) => char.ability_scores.find((s) => s.name === n)?.value ?? 10
  return (char.total_level ?? 0) >= f.min_level
    && (!f.prereq_abilities || f.prereq_abilities.any_of.some((a) => score(a) >= f.prereq_abilities!.min))
    && (!f.needs_spellcasting || char.classes.some((c) => !!c.spellcasting_ability))
}

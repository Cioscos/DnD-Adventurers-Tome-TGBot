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

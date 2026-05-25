import spellsSrd from '@/data/spells-srd.json'

export interface SrdSpell {
  level: number
  casting_time?: string
  range_area?: string
  components?: string
  duration?: string
  damage_dice?: string
  damage_type?: string
  is_concentration?: boolean
  is_ritual?: boolean
  aliases?: string[]
}

type SrdMap = Record<string, SrdSpell | { source: string; note: string }>

// Build a flat name → SrdSpell map at module load (canonical key + every alias).
function buildIndex(): Record<string, SrdSpell> {
  const idx: Record<string, SrdSpell> = {}
  for (const [key, val] of Object.entries(spellsSrd as SrdMap)) {
    if (key.startsWith('_')) continue
    const spell = val as SrdSpell
    idx[key.toLowerCase()] = spell
    for (const alias of spell.aliases ?? []) {
      idx[alias.toLowerCase()] = spell
    }
  }
  return idx
}

const INDEX = buildIndex()

/** Find an SRD entry by canonical English name or Italian alias. */
export function lookupSrdSpell(name: string): SrdSpell | null {
  const key = name.trim().toLowerCase()
  if (!key) return null
  return INDEX[key] ?? null
}

/** Names users can match — used to render a suggestion list. */
export function srdSpellNames(): string[] {
  const out = new Set<string>()
  for (const [key, val] of Object.entries(spellsSrd as SrdMap)) {
    if (key.startsWith('_')) continue
    out.add(key)
    for (const alias of (val as SrdSpell).aliases ?? []) out.add(alias)
  }
  return Array.from(out).sort()
}

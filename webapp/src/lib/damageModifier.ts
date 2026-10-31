import { DAMAGE_TYPES } from '@/pages/inventory/itemMetadata'
import it from '@/locales/it.json'
import en from '@/locales/en.json'

/** Moltiplicatore del danno: metà (resistenza), doppio (vulnerabilità), 0 (immunità).
 *  `null` = nessun override scelto dall'utente. */
export type DamageModifier = 'half' | 'double' | 'none' | 'immune' | null
export type DamageMultiplier = Exclude<DamageModifier, null>

export function applyDamageModifier(value: number, mod: DamageModifier): number {
  if (mod === 'half') return Math.floor(value / 2)
  if (mod === 'double') return value * 2
  if (mod === 'immune') return 0
  return value
}

const SLUGS = DAMAGE_TYPES.filter((d) => d !== 'dmg_other').map((d) => d.replace(/^dmg_/, ''))
const LOOKUP = new Map<string, string>()
for (const slug of SLUGS) {
  LOOKUP.set(slug, slug)
  for (const loc of [it, en]) {
    const label = (loc.character.inventory.damage_types as Record<string, string>)[`dmg_${slug}`]
    if (label) LOOKUP.set(label.toLowerCase(), slug)
  }
}
// Sinonimi digitati a mano nelle vecchie liste (specchio di core/data/damage_types.py).
LOOKUP.set('tagliente', 'slashing').set('perforante', 'piercing').set('radioso', 'radiant')

/** Slug, `dmg_<slug>`, etichetta IT/EN in qualsiasi forma -> slug; ignoto -> null. */
export function canonicalDamageType(value: string | null | undefined): string | null {
  if (typeof value !== 'string') return null
  const v = value.trim().toLowerCase().replace(/^dmg_/, '')
  return LOOKUP.get(v) ?? null
}

export type DamageModifiersMap = Record<string, string[] | undefined> | null | undefined

/** Specchio di `damage_multiplier` lato server: l'immunità prevale,
 *  resistenza + vulnerabilità si annullano. */
export function damageMultiplier(mods: DamageModifiersMap, type: string | null | undefined): DamageMultiplier {
  const slug = canonicalDamageType(type)
  if (!slug || !mods) return 'none'
  const has = (key: string) => (mods[key] ?? []).some((v) => canonicalDamageType(v) === slug)
  if (has('immunities')) return 'immune'
  const res = has('resistances')
  const vul = has('vulnerabilities')
  if (res === vul) return 'none'
  return res ? 'half' : 'double'
}

/** Etichetta tradotta di un tipo salvato (slug o testo legacy); ignoto = testo com'è. */
export function damageTypeLabel(t: (key: string) => string, value: string): string {
  const slug = canonicalDamageType(value)
  return slug ? t(`character.inventory.damage_types.dmg_${slug}`) : value
}

/** Riga di anteprima, es. "Resistenza: 14 → 7". */
export function damagePreviewText(label: string | null, raw: number, applied: number): string {
  return `${label ? `${label}: ` : ''}${raw} → ${applied}`
}

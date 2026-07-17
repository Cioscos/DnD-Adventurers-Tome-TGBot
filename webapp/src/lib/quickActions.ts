import type { CharacterFull, Item, Spell, Ability, CharacterClass } from '@/types'

export const QUICK_ACTIONS_MAX = 12

export const SAVE_ABILITIES = [
  'strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma',
] as const

export type QuickActionEntry =
  | { type: 'weapon'; id: number }
  | { type: 'save'; ability: string }
  | { type: 'spell'; id: number }
  | { type: 'ability'; id: number }
  | { type: 'counter_ability'; id: number }
  | { type: 'counter_inspiration' }
  | { type: 'counter_ammo'; id: number }
  | { type: 'hit_die'; classId: number }
  | { type: 'rest'; rest: 'long' | 'short' }

export type ResolvedQuickAction =
  | { type: 'weapon'; key: string; item: Item }
  | { type: 'save'; key: string; ability: string }
  | { type: 'spell'; key: string; spell: Spell }
  | { type: 'ability'; key: string; ability: Ability }
  | { type: 'counter_ability'; key: string; ability: Ability }
  | { type: 'counter_inspiration'; key: string; active: boolean }
  | { type: 'counter_ammo'; key: string; item: Item }
  | { type: 'hit_die'; key: string; cls: CharacterClass; remaining: number }
  | { type: 'rest'; key: string; rest: 'long' | 'short' }

export function quickActionKey(entry: QuickActionEntry): string {
  switch (entry.type) {
    case 'save': return `save-${entry.ability}`
    case 'counter_inspiration': return 'counter_inspiration'
    case 'hit_die': return `hit_die-${entry.classId}`
    case 'rest': return `rest-${entry.rest}`
    default: return `${entry.type}-${entry.id}`
  }
}

/** Residui dadi vita per classe: level - hit_dice_used, mai negativo. */
export function hitDiceRemaining(cls: CharacterClass): number {
  return Math.max(0, (cls.level ?? 0) - (cls.hit_dice_used ?? 0))
}

export function readQuickActions(settings: Record<string, unknown> | undefined): QuickActionEntry[] {
  const raw = settings?.quick_actions
  return Array.isArray(raw) ? (raw as QuickActionEntry[]) : []
}

/** Un'abilità è pinnabile (azione o contatore) solo se attiva e con usi limitati. */
function isPinnableAbility(a: Ability | undefined): a is Ability {
  return !!a && !a.is_passive && a.max_uses != null
}

/** Risolve le voci salvate contro i dati correnti del personaggio:
 *  scarta le voci stale (arma/incantesimo/abilità eliminati, classe rimossa,
 *  item non più munizione) e i tipi sconosciuti (settings scritti da versioni
 *  future), conserva l'ordine salvato, tronca a QUICK_ACTIONS_MAX. */
export function resolveQuickActions(
  char: CharacterFull,
  entries: QuickActionEntry[],
): ResolvedQuickAction[] {
  const items = new Map((char.items ?? []).map((i) => [i.id, i]))
  const spells = new Map((char.spells ?? []).map((s) => [s.id, s]))
  const abilities = new Map((char.abilities ?? []).map((a) => [a.id, a]))
  const classes = new Map((char.classes ?? []).map((c) => [c.id, c]))
  const saveNames = new Set<string>(SAVE_ABILITIES)

  const resolved: ResolvedQuickAction[] = []
  for (const entry of entries) {
    if (resolved.length >= QUICK_ACTIONS_MAX) break
    const key = quickActionKey(entry)
    switch (entry.type) {
      case 'weapon': {
        const item = items.get(entry.id)
        if (item && item.item_type === 'weapon') resolved.push({ type: 'weapon', key, item })
        break
      }
      case 'save': {
        if (saveNames.has(entry.ability)) resolved.push({ type: 'save', key, ability: entry.ability })
        break
      }
      case 'spell': {
        const spell = spells.get(entry.id)
        if (spell) resolved.push({ type: 'spell', key, spell })
        break
      }
      case 'ability': {
        const ability = abilities.get(entry.id)
        if (isPinnableAbility(ability)) resolved.push({ type: 'ability', key, ability })
        break
      }
      case 'counter_ability': {
        const ability = abilities.get(entry.id)
        if (isPinnableAbility(ability)) resolved.push({ type: 'counter_ability', key, ability })
        break
      }
      case 'counter_inspiration': {
        resolved.push({ type: 'counter_inspiration', key, active: !!char.heroic_inspiration })
        break
      }
      case 'counter_ammo': {
        const item = items.get(entry.id)
        if (item && item.item_type === 'ammunition') resolved.push({ type: 'counter_ammo', key, item })
        break
      }
      case 'hit_die': {
        const cls = classes.get(entry.classId)
        if (cls) resolved.push({ type: 'hit_die', key, cls, remaining: hitDiceRemaining(cls) })
        break
      }
      case 'rest': {
        if (entry.rest === 'long' || entry.rest === 'short') resolved.push({ type: 'rest', key, rest: entry.rest })
        break
      }
      default:
        // Tipo sconosciuto (forward-compat): ignora senza errori.
        break
    }
  }
  return resolved
}

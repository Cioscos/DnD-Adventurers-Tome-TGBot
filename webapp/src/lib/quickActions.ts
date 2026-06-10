import type { CharacterFull, Item, Spell } from '@/types'

export const QUICK_ACTIONS_MAX = 8

export const SAVE_ABILITIES = [
  'strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma',
] as const

export type QuickActionEntry =
  | { type: 'weapon'; id: number }
  | { type: 'save'; ability: string }
  | { type: 'spell'; id: number }

export type ResolvedQuickAction =
  | { type: 'weapon'; key: string; item: Item }
  | { type: 'save'; key: string; ability: string }
  | { type: 'spell'; key: string; spell: Spell }

export function quickActionKey(entry: QuickActionEntry): string {
  return entry.type === 'save' ? `save-${entry.ability}` : `${entry.type}-${entry.id}`
}

export function readQuickActions(settings: Record<string, unknown> | undefined): QuickActionEntry[] {
  const raw = settings?.quick_actions
  return Array.isArray(raw) ? (raw as QuickActionEntry[]) : []
}

/** Risolve le voci salvate contro i dati correnti del personaggio:
 *  scarta le voci stale (arma/incantesimo eliminati, ability sconosciuta),
 *  conserva l'ordine salvato, tronca a QUICK_ACTIONS_MAX. */
export function resolveQuickActions(
  char: CharacterFull,
  entries: QuickActionEntry[],
): ResolvedQuickAction[] {
  const items = new Map((char.items ?? []).map((i) => [i.id, i]))
  const spells = new Map((char.spells ?? []).map((s) => [s.id, s]))
  const abilities = new Set<string>(SAVE_ABILITIES)

  const resolved: ResolvedQuickAction[] = []
  for (const entry of entries) {
    if (resolved.length >= QUICK_ACTIONS_MAX) break
    if (entry.type === 'weapon') {
      const item = items.get(entry.id)
      if (item && item.item_type === 'weapon') {
        resolved.push({ type: 'weapon', key: quickActionKey(entry), item })
      }
    } else if (entry.type === 'save') {
      if (abilities.has(entry.ability)) {
        resolved.push({ type: 'save', key: quickActionKey(entry), ability: entry.ability })
      }
    } else if (entry.type === 'spell') {
      const spell = spells.get(entry.id)
      if (spell) {
        resolved.push({ type: 'spell', key: quickActionKey(entry), spell })
      }
    }
  }
  return resolved
}

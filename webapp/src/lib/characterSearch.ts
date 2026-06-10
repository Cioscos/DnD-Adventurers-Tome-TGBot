import type { CharacterFull } from '@/types'

export type SearchResultType = 'spell' | 'item' | 'ability' | 'note'

export interface SearchResult {
  type: SearchResultType
  id: string
  title: string
  /** Dati grezzi per il sottotitolo — la label i18n la costruisce il componente. */
  meta?: { spellLevel?: number; quantity?: number }
  route: string
}

export const MIN_QUERY_LENGTH = 2
const MAX_PER_TYPE = 8

/** Lowercase + rimozione diacritici: 'Pozione di Velocità' ~ 'velocita'. */
export function normalize(s: string): string {
  return s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
}

/** Body testuale di una nota — il BE salva sia stringhe legacy sia dict
 *  {body, created_at, updated_at, tags} (api/routers/notes.py). I body
 *  "[VOICE:...]" sono path tecnici delle note vocali, non testo cercabile. */
function noteBody(value: unknown): string {
  const body =
    typeof value === 'string'
      ? value
      : typeof value === 'object' && value !== null && typeof (value as { body?: unknown }).body === 'string'
        ? (value as { body: string }).body
        : ''
  return body.startsWith('[VOICE:') ? '' : body
}

/** Ricerca client-side sui contenuti del personaggio (incantesimi, oggetti,
 *  abilità speciali, note). Match `includes` accent-insensitive sul nome —
 *  per le note anche sul corpo. Max 8 risultati per categoria. */
export function searchCharacter(char: CharacterFull, query: string): SearchResult[] {
  const q = normalize(query.trim())
  if (q.length < MIN_QUERY_LENGTH) return []

  const results: SearchResult[] = []
  const matches = (s: string | undefined | null) => typeof s === 'string' && normalize(s).includes(q)

  const spells = (char.spells ?? []).filter((s) => matches(s.name)).slice(0, MAX_PER_TYPE)
  for (const s of spells) {
    results.push({
      type: 'spell',
      id: `spell-${s.id}`,
      title: s.name,
      meta: { spellLevel: s.level },
      route: `/char/${char.id}/spells?focus=${s.id}`,
    })
  }

  const items = (char.items ?? []).filter((i) => matches(i.name)).slice(0, MAX_PER_TYPE)
  for (const i of items) {
    results.push({
      type: 'item',
      id: `item-${i.id}`,
      title: i.name,
      meta: i.quantity > 1 ? { quantity: i.quantity } : undefined,
      route: `/char/${char.id}/inventory`,
    })
  }

  const abilities = (char.abilities ?? []).filter((a) => matches(a.name)).slice(0, MAX_PER_TYPE)
  for (const a of abilities) {
    results.push({
      type: 'ability',
      id: `ability-${a.id}`,
      title: a.name,
      route: `/char/${char.id}/abilities`,
    })
  }

  const notes = Object.entries(char.notes ?? {})
    .filter(([title, value]) => matches(title) || matches(noteBody(value)))
    .slice(0, MAX_PER_TYPE)
  for (const [title] of notes) {
    results.push({
      type: 'note',
      id: `note-${title}`,
      title,
      route: `/char/${char.id}/notes`,
    })
  }

  return results
}

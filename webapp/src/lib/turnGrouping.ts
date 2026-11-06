import { standardActionsFor } from '@/data/standardActions'
import type { ActionType, CharacterFull } from '@/types'

export interface TurnEntry {
  kind: 'weapon' | 'spell' | 'ability' | 'standard'
  id: string
  label: string
}

export interface TurnGroups {
  attacks: TurnEntry[]
  action: TurnEntry[]
  bonus_action: TurnEntry[]
  reaction: TurnEntry[]
  other: TurnEntry[]
}

// Port di core/game/actions.py::parse_casting_time (stessa tabella di casi nei test).
const CASTING_TIME = /^1\s+(?:(azione bonus|bonus action)|(azione|action)|(reazione|reaction))\b/

export function parseCastingTime(text: string | null | undefined): 'action' | 'bonus_action' | 'reaction' | null {
  const m = CASTING_TIME.exec((text ?? '').split(',')[0].trim().toLowerCase())
  if (!m) return null
  return m[1] ? 'bonus_action' : m[2] ? 'action' : 'reaction'
}

export function groupForTurn(char: CharacterFull): TurnGroups {
  const g: TurnGroups = { attacks: [], action: [], bonus_action: [], reaction: [], other: [] }

  for (const it of char.items ?? []) {
    if (it.item_type === 'weapon' && it.is_equipped) g.attacks.push({ kind: 'weapon', id: String(it.id), label: it.name })
  }
  g.attacks.push({ kind: 'weapon', id: 'unarmed', label: 'Colpo senza armi' })

  const noPrep = char.spellcasting?.has_preparing_class === false
  // Campione degli Antichi: gli incantesimi da paladino da 1 azione si lanciano come azione bonus.
  const champion = (char.active_states ?? []).some((s) => s.key === 'elder_champion')
  const paladinRows = new Set((char.classes ?? []).filter((c) => /^(paladin|paladino)$/i.test(c.class_name)).map((c) => c.id))
  // Senza classe (aggiunto a mano) il server lo attribuisce all'unico incantatore del personaggio: qui uguale.
  const casters = char.spellcasting?.casters ?? []
  const onlyCasterIsPaladin = casters.length === 1 && paladinRows.has(casters[0].class_id)
  for (const s of char.spells ?? []) {
    if (!(s.level === 0 || s.is_prepared || noPrep)) continue
    let bucket: keyof TurnGroups = parseCastingTime(s.casting_time) ?? 'other'
    const isPaladinSpell = s.class_id != null ? paladinRows.has(s.class_id) : onlyCasterIsPaladin
    if (champion && bucket === 'action' && isPaladinSpell) bucket = 'bonus_action'
    g[bucket].push({ kind: 'spell', id: String(s.id), label: s.name })
  }

  for (const a of char.abilities ?? []) {
    if (a.is_passive) continue
    const type: ActionType | null | undefined = a.action_type
    const bucket = type === 'action' || type === 'bonus_action' || type === 'reaction' ? type : 'other'
    g[bucket].push({ kind: 'ability', id: String(a.id), label: a.name })
  }

  for (const s of standardActionsFor(char.rules_edition)) g[s.bucket].push({ kind: 'standard', id: s.id, label: s.it.name })
  return g
}

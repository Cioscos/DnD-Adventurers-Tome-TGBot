import type { TurnState } from '@/types'

/** Cosa resta da fare nel turno (U32): attacchi dell'azione Attacco non ancora fatti e azione mai usata. */
export function turnLeftovers(ts: Pick<TurnState, 'turn' | 'attacks_allowed'> | null | undefined): { attacksLeft: number; actionUnused: boolean } {
  const b = ts?.turn
  if (!b) return { attacksLeft: 0, actionUnused: false }
  // Gli attacchi restano solo se l'azione Attacco è cominciata; un'azione extra (Azione Impetuosa) è un'azione ancora da usare.
  const attacksLeft = b.action_attacks > 0 ? Math.max(0, (ts.attacks_allowed ?? 1) - b.action_attacks) : 0
  const actionUnused = (!b.action_used && b.action_attacks === 0) || (b.extra_actions ?? 0) > 0
  return { attacksLeft, actionUnused }
}

import type { Effect, EffectAction, EventType } from '@/lib/homebrew/types'

/** Seed Effect for a freshly-picked action — mirrors the backend defaults. */
export function defaultEffect(action: EffectAction): Effect {
  switch (action) {
    case 'roll_dice':
      return { action, notation: '1d6', store_as: 'result' }
    case 'lookup_table':
      return { action, table: '', row: '', col: '', store_as: 'mapped' }
    case 'match':
      return { action, value: '$result', cases: {} }
    case 'if':
      return { action, cond: { path: '', op: 'eq', value: '' }, then: [] }
    case 'set_property':
      return { action, target: 'subject', key: '', value: '' }
    case 'inc_property':
      return { action, target: 'subject', key: '', delta: 1 }
    case 'unequip':
      return { action, target: 'subject' }
    case 'damage_character':
      return { action, amount: 1 }
    case 'heal_character':
      return { action, amount: 1 }
    case 'change_resource':
      return { action, key: '', delta: -1 }
    case 'restore_resource':
      return { action, key: '', amount: 'max' }
    case 'apply_condition':
      return { action, key: '' }
    case 'remove_condition':
      return { action, key: '' }
    case 'apply_modifier_once':
      // D2: l'engine supporta solo i campi base persistiti hit_points_max/speed.
      return { action, target: 'character.hit_points_max', delta: 1, label: '' }
    case 'notify':
      return { action, severity: 'info', message: '' }
    case 'add_history':
      return { action, description: '' }
  }
}

/**
 * Azioni con restrizione sull'evento del trigger (decisione D1).
 *
 * `apply_modifier_once` applica un delta PERMANENTE alla stat a OGNI innesco
 * (vedi api/services/homebrew/actions.py): ha senso solo su eventi a transizione
 * singola come `level_up` ("+N HP / +N velocità per livello"). Su eventi
 * liberamente ri-attivabili (turn_started, manual_trigger, …) accumulerebbe il
 * delta a ogni tap, corrompendo HP/velocità in modo permanente.
 */
export const ACTION_EVENT_ALLOWLIST: Partial<Record<EffectAction, readonly EventType[]>> = {
  apply_modifier_once: ['level_up'],
}

/** True if `action` may be attached to a trigger on `event` (no entry = unrestricted). */
export function isActionAllowedForEvent(action: EffectAction, event?: EventType): boolean {
  const allowed = ACTION_EVENT_ALLOWLIST[action]
  if (!allowed) return true
  // Evento ignoto (es. EffectChainEditor montato senza contesto): non bloccare
  // qui; la validazione di EffectFormModal resta la rete di sicurezza al salvataggio.
  if (!event) return true
  return allowed.includes(event)
}

// ---------------------------------------------------------------------------
// Amount / compare-value coercion (shared with EffectFormModal)
// ---------------------------------------------------------------------------

// Mirrors the backend amount/dice grammar (api/services/homebrew/actions.py).
export const DICE_REGEX = /^(\d+)d(\d+)([+-]\d+)?$/
// `$name` / `$vars.name` — the bare form without `$` is rejected (the backend
// would read it as dice notation instead).
const VAR_PATH = /^\$(vars\.)?[A-Za-z_][A-Za-z0-9_]*$/
// `N*level` is accepted by _eval_delta ONLY for apply_modifier_once.delta;
// case-insensitive to mirror its `.lower()`.
const LEVEL_EXPR_REGEX = /^-?\d+\*level$/i

export function isAmountValid(raw: string, allowMax: boolean, allowLevel = false): boolean {
  const v = raw.trim()
  if (v === '') return false
  if (allowMax && v === 'max') return true
  if (allowLevel && LEVEL_EXPR_REGEX.test(v)) return true
  if (VAR_PATH.test(v)) return true
  if (DICE_REGEX.test(v)) return true
  const n = Number(v)
  return Number.isFinite(n)
}

export function coerceAmount(raw: string, allowMax: boolean, allowLevel = false): number | string {
  const v = raw.trim()
  if (allowMax && v === 'max') return 'max'
  if (allowLevel && LEVEL_EXPR_REGEX.test(v)) return v
  // Variable references (`$name` / `$vars.name`) pass through verbatim — they
  // must NOT be funneled into Number().
  if (VAR_PATH.test(v)) return v
  if (DICE_REGEX.test(v)) return v
  const n = Number(v)
  return Number.isFinite(n) ? n : v
}

/** Coerce a raw compare-value string to boolean / number / string for the DSL. */
export function coerceCompareValue(raw: string): boolean | number | string {
  const trimmed = raw.trim()
  if (trimmed === 'true') return true
  if (trimmed === 'false') return false
  if (trimmed !== '' && Number.isFinite(Number(trimmed))) return Number(trimmed)
  return raw
}

/**
 * Coerce a comma-separated string into an array for the `in` operator (#7).
 * The backend evaluate_filter rejects a scalar/string rhs for FilterOp.IN and
 * tests `lhs in rhs`, so the value MUST be a list. Each element is coerced like
 * a scalar compare-value; empty items are dropped.
 */
export function coerceListValue(raw: string): (boolean | number | string)[] {
  return raw
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s !== '')
    .map(coerceCompareValue)
}

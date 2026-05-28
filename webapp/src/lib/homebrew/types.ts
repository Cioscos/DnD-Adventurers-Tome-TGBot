/**
 * TypeScript mirror of the homebrew Pydantic DSL.
 *
 * Source of truth: `api/services/homebrew/dsl.py` and
 * `api/schemas/homebrew.py`. Any change in the backend DSL must be
 * reflected here. No runtime code — pure type declarations.
 */

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------

export type FilterOp =
  | "eq"
  | "neq"
  | "lt"
  | "lte"
  | "gt"
  | "gte"
  | "in"
  | "has_property"

export interface Filter {
  path: string
  op: FilterOp
  value: unknown
}

// ---------------------------------------------------------------------------
// Subject
// ---------------------------------------------------------------------------

export type SubjectType = "item" | "character" | "ability"

export interface SubjectFilter {
  item_types?: string[]
  name_contains?: string
}

export interface Subject {
  type: SubjectType
  filter?: SubjectFilter
}

// ---------------------------------------------------------------------------
// Property
// ---------------------------------------------------------------------------

export type PropertyType = "enum" | "number" | "boolean" | "text"

export interface Property {
  key: string
  type: PropertyType
  values?: string[]
  default: unknown
  label_i18n: Record<string, string>
  value_labels_i18n?: Record<string, Record<string, string>>
}

// ---------------------------------------------------------------------------
// Table
// ---------------------------------------------------------------------------

export type ColBin = [number, number]

export interface Table {
  id: string
  row_axis: string
  col_axis: string
  col_bins: ColBin[]
  cells: Record<string, string[]>
}

// ---------------------------------------------------------------------------
// Passive modifier
// ---------------------------------------------------------------------------

export interface PassiveModifier {
  when: Filter
  target: string
  value: number | string
  label_i18n: Record<string, string>
}

// ---------------------------------------------------------------------------
// Resource definition
// ---------------------------------------------------------------------------

export type RestorationType = "long_rest" | "short_rest" | "none"

export interface ResourceDef {
  key: string
  name: string
  max: number
  restoration_type: RestorationType
}

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------

export type EventType =
  | "attack_rolled"
  | "damage_taken"
  | "dropped_to_zero"
  | "hp_healed"
  | "long_rest_taken"
  | "short_rest_taken"
  | "spell_cast"
  | "ability_used"
  | "item_equipped"
  | "item_unequipped"
  | "level_up"
  | "resource_changed"
  | "resource_depleted"
  | "turn_started"
  | "manual_trigger"

export interface Trigger {
  event: EventType
  filters: Filter[]
  effects: Effect[]
}

// ---------------------------------------------------------------------------
// Effects (discriminated union — keep exhaustive)
// ---------------------------------------------------------------------------

export type EffectTarget = "subject" | "character"

export type NumberOrExpr = number | string

export interface RollDiceEffect {
  action: "roll_dice"
  notation: string
  store_as: string
}

export interface LookupTableEffect {
  action: "lookup_table"
  table: string
  row: string
  col: string
  store_as: string
}

export interface MatchEffect {
  action: "match"
  value: string
  cases: Record<string, Effect[]>
}

export interface IfEffect {
  action: "if"
  cond: Filter
  then: Effect[]
  else?: Effect[]
}

export interface SetPropertyEffect {
  action: "set_property"
  target: EffectTarget
  key: string
  value: unknown
}

export interface IncPropertyEffect {
  action: "inc_property"
  target: EffectTarget
  key: string
  delta: NumberOrExpr
}

export interface UnequipEffect {
  action: "unequip"
  target: "subject"
}

export interface DamageCharacterEffect {
  action: "damage_character"
  amount: NumberOrExpr
  type?: string
  was_critical?: boolean
}

export interface HealCharacterEffect {
  action: "heal_character"
  amount: NumberOrExpr
}

export interface ChangeResourceEffect {
  action: "change_resource"
  key: string
  delta: NumberOrExpr
}

export interface RestoreResourceEffect {
  action: "restore_resource"
  key: string
  amount: NumberOrExpr | "max"
}

export interface ApplyConditionEffect {
  action: "apply_condition"
  key: string
  params?: Record<string, unknown>
}

export interface RemoveConditionEffect {
  action: "remove_condition"
  key: string
}

export interface ApplyModifierOnceEffect {
  action: "apply_modifier_once"
  target: string
  delta: NumberOrExpr
  label: string
}

export type NotifySeverity = "info" | "warning" | "error" | "success"

export interface NotifyEffect {
  action: "notify"
  severity: NotifySeverity
  message: string
}

export interface AddHistoryEffect {
  action: "add_history"
  description: string
  meta?: Record<string, unknown>
}

export type Effect =
  | RollDiceEffect
  | LookupTableEffect
  | MatchEffect
  | IfEffect
  | SetPropertyEffect
  | IncPropertyEffect
  | UnequipEffect
  | DamageCharacterEffect
  | HealCharacterEffect
  | ChangeResourceEffect
  | RestoreResourceEffect
  | ApplyConditionEffect
  | RemoveConditionEffect
  | ApplyModifierOnceEffect
  | NotifyEffect
  | AddHistoryEffect

export type EffectAction = Effect["action"]

// ---------------------------------------------------------------------------
// Top-level Rule DSL
// ---------------------------------------------------------------------------

export interface RuleDSL {
  version: 1
  subject: Subject
  properties?: Property[]
  tables?: Table[]
  passive_modifiers?: PassiveModifier[]
  triggers?: Trigger[]
  resources?: ResourceDef[]
}

// ---------------------------------------------------------------------------
// API shapes — homebrew rules CRUD
// ---------------------------------------------------------------------------

export interface HomebrewRule {
  id: number
  character_id: number
  name: string
  description: string | null
  enabled: boolean
  dsl: RuleDSL
  version: number
  template_id: string | null
  created_at: string
  updated_at: string
}

export interface HomebrewRuleCreate {
  name: string
  description?: string | null
  enabled?: boolean
  dsl: RuleDSL
  template_id?: string | null
}

export interface HomebrewRuleUpdate {
  name?: string
  description?: string | null
  enabled?: boolean
  dsl?: RuleDSL
  template_id?: string | null
}

// ---------------------------------------------------------------------------
// API shapes — resources, templates, notifications
// ---------------------------------------------------------------------------

export interface HomebrewResource {
  id: number
  rule_id: number
  character_id: number
  key: string
  name: string
  current: number
  max: number
  restoration_type: RestorationType
}

export interface TemplateRead {
  id: string
  name: string
  description: string
  icon: string
}

export interface TemplateDetailRead extends TemplateRead {
  dsl: RuleDSL
}

export interface NotificationRead {
  severity: NotifySeverity
  message: string
  rule_id: number | null
  rule_name: string | null
}

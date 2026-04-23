/** TypeScript types mirroring the FastAPI Pydantic schemas. */

export type AbilityName =
  | 'strength'
  | 'dexterity'
  | 'constitution'
  | 'intelligence'
  | 'wisdom'
  | 'charisma'

export type AbilityModifierKind = 'absolute' | 'relative'

export interface AbilityModifier {
  ability: AbilityName
  kind: AbilityModifierKind
  value: number
}

export interface AppliedModifier {
  source: string
  ability: AbilityName
  kind: AbilityModifierKind
  value: number
  item_id: number
}

export interface AbilityScore {
  id: number
  name: AbilityName | string
  value: number
  base_value?: number
  modifier: number
  modifiers_applied?: AppliedModifier[]
}

export interface ClassResource {
  id: number
  name: string
  current: number
  total: number
  restoration_type: string
  note?: string
}

export interface CharacterClass {
  id: number
  class_name: string
  level: number
  subclass?: string
  spellcasting_ability?: string
  hit_die?: number
  resources: ClassResource[]
}

export interface Currency {
  id: number
  copper: number
  silver: number
  electrum: number
  gold: number
  platinum: number
}

export interface Ability {
  id: number
  name: string
  description?: string
  max_uses?: number
  uses?: number
  is_passive: boolean
  is_active: boolean
  restoration_type: string
}

export interface MapEntry {
  id: number
  zone_name: string
  file_id: string
  file_type: string
  local_file_path?: string | null
}

export interface Spell {
  id: number
  name: string
  level: number
  description?: string
  casting_time?: string
  range_area?: string
  components?: string
  duration?: string
  is_concentration: boolean
  is_ritual: boolean
  higher_level?: string
  attack_save?: string
  damage_dice?: string
  damage_type?: string
  is_pinned: boolean
}

export interface SpellSlot {
  id: number
  level: number
  total: number
  used: number
  available: number
}

export interface Item {
  id: number
  name: string
  description?: string
  weight: number
  quantity: number
  item_type: string
  item_metadata?: Record<string, unknown>
  is_equipped: boolean
}

export interface CharacterSummary {
  id: number
  name: string
  race?: string
  gender?: string
  hit_points: number
  current_hit_points: number
  temp_hp: number
  ac: number
  total_level: number
  class_summary: string
  heroic_inspiration: boolean
  experience_points: number
}

export interface ConcentrationSaveResult {
  die: number
  bonus: number
  total: number
  description?: string
  dc: number
  success: boolean
  lost_concentration: boolean
  is_critical: boolean
  is_fumble: boolean
}

export interface CharacterFull extends CharacterSummary {
  background?: string
  alignment?: string
  speed: number
  base_armor_class: number
  shield_armor_class: number
  magic_armor: number
  carry_capacity: number
  encumbrance: number
  spell_slots_mode: string
  concentrating_spell_id?: number
  hp_gained?: number
  concentration_save?: ConcentrationSaveResult | null
  rolls_history?: DiceRollResult[]
  notes?: Record<string, string>
  settings?: Record<string, unknown>
  conditions?: Record<string, unknown>
  skills?: Record<string, unknown>
  saving_throws?: Record<string, boolean>
  death_saves?: DeathSaves
  personality?: Record<string, string>
  languages?: string[]
  general_proficiencies?: string[]
  damage_modifiers?: Record<string, string[]>
  classes: CharacterClass[]
  ability_scores: AbilityScore[]
  spells: Spell[]
  spell_slots: SpellSlot[]
  items: Item[]
  currency?: Currency
  abilities: Ability[]
  maps: MapEntry[]
}

export interface DeathSaves {
  successes: number
  failures: number
  stable: boolean
}

export interface DiceRollResult {
  notation: string
  rolls: number[]
  total: number
  modifier?: number
}

export interface HistoryEntry {
  id: number
  timestamp: string
  event_type: string
  description: string
}

export interface Note {
  title: string
  body: string
  is_voice: boolean
}

export type SessionRole = 'game_master' | 'player'
export type SessionStatus = 'active' | 'closed'

export interface SessionParticipant {
  user_id: number
  role: SessionRole
  character_id?: number | null
  display_name?: string | null
  joined_at: string
}

export interface GameSession {
  id: number
  code: string
  gm_user_id: number
  status: SessionStatus
  title?: string | null
  created_at: string
  last_activity_at: string
  closed_at?: string | null
  participants: SessionParticipant[]
}

export type HpBucket = 'healthy' | 'lightly_wounded' | 'badly_wounded' | 'dying' | 'dead'
export type ArmorCategory = 'unarmored' | 'light' | 'medium' | 'heavy'

export interface CharacterLiveSnapshot {
  id: number
  name: string
  race?: string | null
  class_summary: string
  total_level: number
  hit_points: number | null
  current_hit_points: number | null
  temp_hp: number | null
  ac: number | null
  conditions?: Record<string, unknown> | null
  death_saves?: Record<string, unknown> | null
  heroic_inspiration: boolean
  last_roll?: DiceRollResult | null
  hp_bucket: HpBucket | null
  armor_category: ArmorCategory | null
}

export interface GameSessionLive extends GameSession {
  live_characters: CharacterLiveSnapshot[]
}

export interface SessionMessage {
  id: number
  user_id: number
  role: SessionRole
  body: string
  sent_at: string
  recipient_user_id?: number | null
  sender_display_name?: string | null
}

export interface RollDamageRequest {
  casting_level?: number
  extra_dice?: string
  is_critical?: boolean
}

export interface RollDamageResult {
  rolls: number[]
  total: number
  half_damage: number
  damage_type: string | null
  breakdown: string
  casting_level: number
  is_critical: boolean
}

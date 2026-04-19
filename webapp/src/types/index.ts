/** TypeScript types mirroring the FastAPI Pydantic schemas. */

export interface AbilityScore {
  id: number
  name: string
  value: number
  modifier: number
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

export interface CharacterLiveSnapshot {
  id: number
  name: string
  race?: string | null
  class_summary: string
  total_level: number
  hit_points: number
  current_hit_points: number
  temp_hp: number
  ac: number
  conditions?: Record<string, unknown>
  death_saves?: Record<string, unknown>
  heroic_inspiration: boolean
  last_roll?: DiceRollResult | null
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
}

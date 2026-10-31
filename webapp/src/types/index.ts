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

export interface CharacterClass {
  id: number
  class_name: string
  level: number
  subclass?: string
  spellcasting_ability?: string
  hit_die?: number
  /** Dadi vita spesi (residui = level - hit_dice_used). */
  hit_dice_used?: number
}

export interface Currency {
  id: number
  copper: number
  silver: number
  electrum: number
  gold: number
  platinum: number
}

export type ActionType = 'action' | 'bonus_action' | 'reaction' | 'free' | 'special'

export interface PendingChoice {
  id: string
  kind: 'asi'
  class_key: string
  level: number
  created_at: string
}

export type ResolveChoiceBody =
  | { kind: 'asi'; increases: Record<string, number> }
  | { kind: 'feat'; feat_key: string; ability?: string | null; custom_name?: string | null; custom_text?: string | null }

export interface Ability {
  id: number
  name: string
  description?: string
  max_uses?: number
  uses?: number
  is_passive: boolean
  is_active: boolean
  restoration_type: string
  /** Feature auto-generata da una classe: link alla classe e chiave di catalogo. */
  source_class_id?: number | null
  is_class_feature: boolean
  feature_key?: string | null
  action_type?: ActionType | null
}

export interface MapEntry {
  id: number
  zone_name: string
  file_id: string
  file_type: string
  local_file_path?: string | null
  position?: number
  size_bytes?: number
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
  attack_save?: string | null
  damage_dice?: string
  damage_type?: string
  is_pinned: boolean
  is_prepared: boolean
  school?: string | null
  srd_index?: string | null
  higher_levels_dice?: string | null
}

export interface SpellSlot {
  id: number
  level: number
  total: number
  used: number
  available: number
  /** True = Warlock Pact Magic slot (separate pool, recovers on a short rest). */
  is_pact: boolean
}

export type EquipmentSlot =
  | 'head' | 'neck' | 'cloak' | 'body' | 'hands'
  | 'ring1' | 'ring2' | 'feet'
  | 'main_hand' | 'off_hand' | 'ammunition'

export interface Item {
  id: number
  name: string
  description?: string
  weight: number
  quantity: number
  item_type: string
  item_metadata?: Record<string, unknown>
  is_equipped: boolean
  equipment_slot?: EquipmentSlot | null
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
  hp_max_homebrew_modifier: number
  ac_homebrew_modifier: number
  ac_items_modifier?: number
  is_dead: boolean
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

export interface ConsumableUse {
  heal_rolls: number[]
  total_healed: number
  conditions_added: string[]
  conditions_removed: string[]
}

export interface AcBreakdown {
  base: number
  shield: number
  magic: number
  homebrew: number
  /** Bonus CA da oggetti magici attivi (equipaggiati/sintonizzati). */
  items?: number
}

/** Blocco derivato dal BE: preparazione incantesimi + capacità rituali. */
export interface SpellcastingInfo {
  has_preparing_class: boolean
  prepared_cap: number | null
  prepared_count: number
  cap_mode: 'auto' | 'manual'
  has_ritual_caster: boolean
  has_wizard: boolean
  casters: { class_id: number; class_name: string; ability: string; save_dc: number; attack_bonus: number }[]
}

// Il dettaglio backend non restituisce ac_homebrew_modifier (solo la lista): resta opzionale
// e CharacterFull non è assegnabile a CharacterSummary, così effectiveAc non gira su di esso.
export interface ConditionEffect {
  slug: string
  expiry_anchor?: 'owner' | 'source' | null
  expiry_edge?: 'start' | 'end' | null
  expiry_count?: number | null
  save_ability?: string | null
  save_dc?: number | null
  save_edge?: 'start' | 'end' | null
  source_name?: string | null
  ends_with_concentration: boolean
  applied_by_gm: boolean
}

export interface PendingSave {
  id: number
  slug: string
  ability: string
  dc: number
  status: 'pending' | 'failed' | 'passed'
  created_at: string
  last_roll?: Record<string, unknown> | null
}

export interface PendingSaveRollResult {
  save: PendingSave
  roll: import('@/api/client').RollResult
  passed: boolean
  condition_removed: boolean
}

export interface CharacterFull extends Omit<CharacterSummary, 'ac_homebrew_modifier'> {
  ac_homebrew_modifier?: number
  condition_effects?: ConditionEffect[]
  pending_saves?: PendingSave[]
  background?: string
  alignment?: string
  speed: number
  base_armor_class: number
  shield_armor_class: number
  magic_armor: number
  base_armor_class_override: boolean
  shield_armor_class_override: boolean
  unarmored_defense_ability?: 'wisdom' | 'constitution' | null
  ac_breakdown?: AcBreakdown | null
  speed_homebrew_modifier?: number
  speed_items_modifier?: number
  /** DEX effettiva + bonus iniziativa da oggetti: stesso valore usato per il tiro. */
  initiative_bonus?: number
  skills_homebrew_modifiers?: Record<string, number>
  saves_homebrew_modifiers?: Record<string, number>
  saves_items_modifiers?: Record<string, number>
  /** Totali calcolati dal server (stesso valore del tiro): bonus abilità e punteggi passivi. */
  skill_bonuses?: Record<string, number>
  passives?: Record<string, number>
  /** Tuttofare (Bardo >= 2): mezza competenza sulle abilità non competenti. */
  jack_of_all_trades?: boolean
  carry_capacity: number
  carry_capacity_override: boolean
  has_custom_silhouette: boolean
  attacks_per_action?: number
  /** Forma selvatica attiva: PF/CA della forma sostituiscono quelli del personaggio. */
  active_form?: ActiveForm | null
  /** Solo da POST /rounds/tick: etichette degli effetti appena scaduti. */
  expired_effects?: string[] | null
  encumbrance: number
  /** Oggetti (+ monete se attivo) calcolati dal server: unica fonte per Inventario, Equipaggiamento ed Eroe. */
  encumbrance_total?: number
  encumbrance_level?: 'none' | 'encumbered' | 'heavily'
  speed_encumbrance_penalty_ft?: number
  spell_slots_mode: string
  spellcasting?: SpellcastingInfo | null
  concentrating_spell_id?: number
  hp_gained?: number
  /** Scelte di livello in sospeso (aumento caratteristiche / talento). */
  pending_choices?: PendingChoice[] | null
  concentration_save?: ConcentrationSaveResult | null
  /** Id dello snapshot per annullare l'ultima modifica PF; null se nulla è cambiato. */
  hp_undo_id?: string | null
  homebrew_notifications?: Array<Record<string, unknown>> | null
  rolls_history?: DiceRollResult[]
  /** Raw dal BE: valore stringa legacy oppure dict {body, created_at, updated_at, tags}. */
  notes?: Record<
    string,
    string | { body?: string; created_at?: string | null; updated_at?: string | null; tags?: string[] }
  >
  settings?: Record<string, unknown>
  conditions?: Record<string, unknown>
  skills?: Record<string, unknown>
  saving_throws?: Record<string, boolean>
  death_saves?: DeathSaves
  personality?: Record<string, string>
  languages?: string[]
  general_proficiencies?: Partial<Record<'armor' | 'weapons' | 'tools' | 'other', string[]>> | string[]
  damage_modifiers?: Record<string, string[]>
  classes: CharacterClass[]
  ability_scores: AbilityScore[]
  spells: Spell[]
  spell_slots: SpellSlot[]
  items: Item[]
  consumable_use?: ConsumableUse | null
  currency?: Currency
  abilities: Ability[]
  maps: MapEntry[]
}

export interface DeathSaves {
  successes: number
  failures: number
  stable: boolean
}

export type DiceSource = 'manual' | 'weapon' | 'skill' | 'save' | 'spell' | 'init'

export interface DiceRollResult {
  notation: string
  rolls: number[]
  total: number
  modifier?: number
  timestamp?: string | null
  source?: DiceSource | string | null
  label?: string | null
}

export interface HistoryEntry {
  id: number
  timestamp: string
  event_type: string
  description: string
}

export interface HistoryRetentionPreview {
  total: number
  events_keep: number
  days_window: number
  would_purge_events: number
  would_purge_days: number
}

export interface Note {
  title: string
  body: string
  is_voice: boolean
  created_at?: string | null
  updated_at?: string | null
  tags?: string[]
}

export interface SharePreview {
  kind: 'item' | 'note'
  title: string
  description?: string | null
  is_voice: boolean
  item_type?: string | null
  quantity?: number | null
  sender_char_name: string
}

export interface ShareImportResult {
  ok: boolean
  kind: 'item' | 'note'
  char_id: number
  title: string
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
  gm_display_name?: string | null
  status: SessionStatus
  title?: string | null
  created_at: string
  /** Keep-alive del server: cambia a ogni GET di /live, quindi SessionRoom
   *  lo scarta prima della cache (structural sharing); può mancare. */
  last_activity_at?: string
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

export type EncounterMode = 'light' | 'full'
export type EncounterStatus = 'setup' | 'active' | 'ended'

export interface CombatantLive {
  id: number
  kind: 'pc' | 'monster'
  character_id?: number | null
  owner_user_id?: number | null
  name: string
  initiative: number | null
  initiative_die: number | null
  initiative_mod: number
  sort_order: number | null
  is_dead: boolean
  conditions: Record<string, unknown>
  current_hp: number | null
  max_hp: number | null
  ac: number | null
  hp_bucket: HpBucket | null
}

export interface EncounterLive {
  id: number
  mode: EncounterMode
  status: EncounterStatus
  round: number
  active_combatant_id: number | null
  created_at: string
  started_at: string | null
  ended_at: string | null
  combatants: CombatantLive[]
}

export interface CombatantPatch {
  name?: string
  initiative?: number
  initiative_mod?: number
  current_hp?: number
  max_hp?: number
  ac?: number
  conditions?: Record<string, unknown>
  is_dead?: boolean
}

export interface GameSessionLive extends GameSession {
  live_characters: CharacterLiveSnapshot[]
  encounter?: EncounterLive | null
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

export interface ParticipantIdentity {
  user_id: number
  character_id: number
  name: string
  race: string | null
  gender: string | null
  alignment: string | null
  speed: number | null
  languages: string | null
  general_proficiencies: string | null
  background: string | null
  personality_traits: string | null
  ideals: string | null
  bonds: string | null
  flaws: string | null
  show_private: boolean
}

export interface RollDamageRequest {
  casting_level?: number
  extra_dice?: string
  is_critical?: boolean
  main_rolls?: number[]
  extra_rolls?: number[]
}

/** Esito di POST /characters/{id}/spells/{spell_id}/attack. */
export interface SpellAttackResult {
  spell_name: string
  to_hit_die: number
  dice?: number[]
  mode?: 'normal' | 'advantage' | 'disadvantage'
  to_hit_bonus: number
  to_hit_total: number
  is_critical: boolean
  is_fumble: boolean
  caster_class: string | null
  character: CharacterFull
  homebrew_notifications?: Array<Record<string, unknown>> | null
}

export interface SpellAttackRequest {
  slot_level: number | null
  ritual?: boolean
  die?: number
  dice?: number[]
  mode?: 'normal' | 'advantage' | 'disadvantage'
  with_inspiration?: boolean
}

export interface RollDamageResult {
  rolls: number[]
  total: number
  half_damage: number
  damage_type: string | null
  breakdown: string
  casting_level: number
  is_critical: boolean
  scaled_dice?: string
  main_kind: string
  main_rolls: number[]
  extra_kind: string | null
  extra_rolls: number[]
}

export interface SessionFeedItem {
  type: 'message' | 'event'
  timestamp: string

  // message
  message_id?: number | null
  user_id?: number | null
  display_name?: string | null
  role?: string | null
  body?: string | null
  recipient_user_id?: number | null
  // message — GM grant payload
  item_id?: number | null
  item_name?: string | null
  item_quantity?: number | null

  // event
  event_id?: number | null
  character_id?: number | null
  character_name?: string | null
  owner_user_id?: number | null
  event_type?: string | null
  description?: string | null
  op?: string | null
}

export interface SessionFeedResponse {
  items: SessionFeedItem[]
  has_more: boolean
}

export interface TurnState {
  in_encounter: boolean
  is_my_turn: boolean
  round: number | null
  session_id: number | null
  pending_saves?: PendingSave[]
}

export interface ActiveForm {
  companion_id: number
  name: string
  current_hp: number
  max_hp: number
  temp_hp: number
  armor_class: number
}

export type CompanionKind = 'familiar' | 'companion' | 'mount' | 'summon' | 'wild_shape'

export interface CompanionAction {
  name: string
  desc?: string
  attack_bonus?: number | null
  damage_dice?: string | null
  damage_type?: string | null
  /** Testo mancante in italiano: mostrato in inglese con badge EN. */
  en?: boolean
}

export interface CompanionStatblock {
  size?: string
  type?: string
  speed?: Record<string, number>
  abilities?: Record<string, number>
  traits?: CompanionAction[]
  actions?: CompanionAction[]
  challenge_rating?: number
  [key: string]: unknown
}

export interface Companion {
  id: number
  character_id: number
  kind: CompanionKind
  name: string
  srd_index: string | null
  statblock: CompanionStatblock
  max_hp: number
  current_hp: number
  temp_hp: number
  armor_class: number
  notes: string | null
  is_active: boolean
  created_at: string
  down: boolean
}

export type CompanionPayload = Partial<Pick<Companion,
  'kind' | 'name' | 'srd_index' | 'statblock' | 'max_hp' | 'current_hp' | 'temp_hp' | 'armor_class' | 'notes' | 'is_active'>>

export interface CompanionAttackResult {
  to_hit_die: number
  to_hit_bonus: number
  to_hit_total: number
  dice: number[]
  mode: 'normal' | 'advantage' | 'disadvantage'
  is_critical: boolean
  damage_rolls: number[]
  damage_total: number
  damage_type: string | null
}

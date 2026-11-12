import type { OptionResult, RollChoice, RollOption } from '@/api/client'

/** TypeScript types mirroring the FastAPI Pydantic schemas. */

export type AbilityName =
  | 'strength'
  | 'dexterity'
  | 'constitution'
  | 'intelligence'
  | 'wisdom'
  | 'charisma'

export type AbilityModifierKind = 'absolute' | 'relative'

/** Cosa si può togliere e a chi (Task 48): lo stesso per un incantesimo e per un privilegio. */
export type RemovalInfo = {
  count: number | null; max_targets: number; ally: boolean
  optional?: boolean; bound?: boolean; modes?: string[] | null; cost_each?: number
  conditions: { key: string; label: { it: string; en: string } }[]; untracked: { key: string; label: { it: string; en: string } }[]
}

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
  /** Chiave di catalogo riconosciuta dal testo; null per testo libero. */
  subclass_key?: string | null
  /** Opzioni di classe scelte: {gruppo: [chiave]}. */
  options?: Record<string, string[]>
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

export interface ClassOptionEntry {
  key: string
  name: { it: string; en: string }
  summary: { it: string; en: string }
  /** Già sulla scheda di un personaggio salvato prima del catalogo: si dichiara, non si aggiunge (R39). */
  owned?: boolean
}

export interface ClassOptionsState {
  replaceable: boolean
  /** Il gruppo si mostra nella pagina della classe anche se non si può sostituire. */
  listed?: boolean
  chosen: ClassOptionEntry[]
  available: ClassOptionEntry[]
}

export interface PendingChoice {
  id: string
  kind: 'asi' | 'feat' | 'class_option' | 'epic_boon'
  class_key: string
  level: number
  created_at: string
  /** Solo class_option: gruppo, quante opzioni scegliere e quelle ancora disponibili. */
  group?: string
  count?: number
  options?: ClassOptionEntry[]
  /** Quante opzioni si prendono adesso: meno di `count` se la scheda non ne offre abbastanza, il resto aspetta (R39). */
  pick_count?: number | null
  /** Falso se non c'è ancora nulla da scegliere: non blocca le scelte successive. */
  resolvable?: boolean
  /** Personaggio salvato prima del catalogo o importato: ammette ciò che ha già sulla scheda (R39). */
  retrofit?: boolean
  /** Solo incantesimi a scelta (Segreti Magici): si scelgono dalla pagina degli incantesimi; `free`: non contano fra i conosciuti.
   *  `list`: la classe del cui elenco si pesca (trucchetto del druido), `null` per qualsiasi classe.
   *  `owned`: con `retrofit`, gli incantesimi già conosciuti che si possono dichiarare «già sulla scheda». */
  spell_pick?: { free: boolean; max_level: number; exact?: boolean; ritual?: boolean; book?: boolean; list?: string | null; school?: string | null; owned?: { id: number; name: string; level: number }[] }
}

export type ResolveChoiceBody =
  | { kind: 'asi'; increases: Record<string, number> }
  | { kind: 'feat'; feat_key: string; ability?: string | null; custom_name?: string | null; custom_text?: string | null }
  | { kind: 'epic_boon'; feat_key: string; ability?: string | null }
  | { kind: 'class_option'; options: string[] }

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
  /** Il «Usa» passa da POST /features/{key}/use (cura, stato, azione extra) invece di scalare solo il contatore. */
  has_on_use?: boolean
  /** Il «Usa» ora non costa nulla e si può fare (prolungare l'Ira): acceso anche a 0 usi. Lo decide il server. */
  free_use?: boolean
  /** Il «Usa» ora verrebbe rifiutato dal server (Rompi-Incantesimi senza un lancio da rendere): il pulsante è spento. */
  use_blocked?: boolean
  /** Il «Usa» dà lo stato a un altro personaggio della serata (Ispirazione Bardica): si chiede a chi (R38). */
  gives_to_ally?: boolean
  /** Valori della scelta `mode` rivolti a un'altra creatura (Imposizione delle Mani): il client chiede a chi. */
  ally_modes?: string[]
  /** Il «Usa» toglie condizioni nel foglio comune (Task 48), già filtrato per questo personaggio. */
  removal?: RemovalInfo | null
  /** Con `gives_to_ally` per PF temporanei: quante creature della serata può raggiungere il «Usa» (Mantello di Ispirazione: più d'una). */
  ally_max?: number
  /** Tipi di danno che il riposo accetta per la resistenza di questo privilegio (Resilienza Immonda). */
  rest_damage_choices?: string[]
  /** Cosa farà il «Usa» (Astuzia Magica: quanti slot di Patto tornano), calcolato dal server. */
  use_preview?: { it: string; en: string } | null
  /** Pool: il giocatore sceglie quanti usi spendere, al massimo `max_amount` (null: gli usi rimasti). */
  choose_amount?: boolean
  max_amount?: number | null
  /** Scelte sì/no da fare all'uso (Frenesia all'ingresso in ira), già filtrate per questo personaggio. */
  use_toggles?: { key: string; label: { it: string; en: string } }[]
  /** Scelte fra più valori da fare all'uso (l'abilità di Conoscenze Secolari). */
  /** L'uso passa da un pannello proprio (Preservare Vita), non da `POST /features/{key}/use`. */
  use_panel?: string | null
  /** Usi che restano al privilegio di cui questo spende gli usi (la riserva di Incanalare Divinità). */
  spends_left?: number | null
  /** Riserva a catalogo (Incanalare Divinità): solo contatore, senza «Usa». */
  is_pool?: boolean
  use_choices?: { key: string; label: { it: string; en: string }; options: { key: string; label: { it: string; en: string } }[]; optional?: boolean }[]
  /** Testi liberi da scrivere all'uso (il nome di un'identità falsa, di un incantesimo rubato). */
  use_texts?: { key: string; label: { it: string; en: string }; max_len: number; optional?: boolean }[]
  /** CD dei tiri salvezza del privilegio, calcolata dal server (il ki del Monaco: 8 + competenza + Saggezza). */
  dc?: number | null
  /** Usi minimi da spendere insieme (Frusta d'Acqua: 2 ki). */
  min_amount?: number
}

/** Stato avviato da un privilegio (Ira...): finisce per round, riposo, svenimento o a mano. */
export interface ActiveState {
  key: string
  feature_key: string
  /** Come lo chiama il giocatore; assente negli stati avviati prima che il server lo salvasse. */
  name?: string | null
  rounds_left: number | null
  ends_on: string[]
  data: Record<string, unknown>
}

export interface ZeroHpSaveResult {
  feature_key: string
  ability: string
  die: number
  bonus: number
  total: number
  dc: number
  success: boolean
  hp: number
}

export interface FeatureUseResult {
  rolls: number[]
  healed: number
  state: ActiveState | null
  notes: string[]
  /** Chiavi con un effetto su altri da applicare (`TargetEffectSheet`), per esempio Presenza Intimidatoria. */
  targets?: string[]
  /** Valore da dare a un altro, mai scritto sulla scheda (PF temporanei di Incoraggiamento). */
  given?: number | null
  /** Chi ha ricevuto una cura dal privilegio (Imposizione delle Mani su un compagno della serata). */
  received?: { name: string; healed: number } | null
  /** PF temporanei consegnati ad altri PG della serata: `given` offerti, `temp_hp` ora sulla scheda, `applied` falso se ne avevano di più. */
  temp_received?: { name: string; given: number; temp_hp: number; applied: boolean }[]
  /** PF temporanei che il privilegio ha dato a chi lo usa (Benedizione dell'Oscuro, Vigore Immondo). */
  temp_hp?: number | null
  /** Esiti delle condizioni tolte (Task 48), nelle due lingue. */
  removal?: { it: string; en: string }[]
  /** Esito scritto dal privilegio nelle due lingue (ore dimenticate di Alterare Ricordi, danno residuo dell'Interdizione). */
  message?: { it: string; en: string } | null
  /** Tiro per colpire di un privilegio che attacca (Arciere): senza danno se `is_fumble`, dadi doppi se `is_critical`. */
  attack?: { die: number; bonus: number; total: number; is_critical: boolean; is_fumble: boolean } | null
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

export interface SpellEffectInfo {
  target_kind: 'self' | 'ally' | 'allies' | 'aura'
  /** Il lancio sceglie un'arma non magica del bersaglio (Arma Magica, Arma Elementale): `choices.item_id`. */
  weapon_choice?: boolean
  /** Punizione: il danno lo dà l'opzione al colpo, il lancio non tira i dadi dell'incantesimo. */
  hit_damage?: boolean
  /** Tipi di arma sceglibili (chiavi di `WEAPONS`: Randello Incantato); assente: qualunque arma non magica. */
  weapon_kinds?: string[]
  /** Il tipo dei dadi in più dello slot più alto scelto all'ultimo lancio (Colpo Infuocato, Fame di Hadar); il server lo conserva. */
  cast_upcast_type?: string | null
  max_targets_by_slot: Record<string, number>
  /** `when`: si chiede solo se la scelta `[chiave, valore]` è già stata fatta (il tipo delle Rune Esplosive del Glifo). */
  choices: { key: string; label: { it: string; en: string }; options: string[]; when?: [string, string] | null }[]
}

/** Esito degli effetti di un lancio: bersagli che hanno ricevuto lo stato e, fuori serata, il testo per il GM. */
export interface SpellEffectsResult {
  applied: { id: number; name: string }[]
  text?: { it: string; en: string } | null
}

export interface Spell {
  id: number
  name: string
  level: number
  description?: string
  casting_time?: string
  /** Tempo di lancio che vale ora (il server lo porta ad azione bonus con Campione degli Antichi, Rompi-Incantesimi): solo da mostrare e raggruppare; il form usa `casting_time`. */
  effective_casting_time?: string
  range_area?: string
  components?: string
  /** Gittata e componenti che valgono ora (privilegi che le cambiano): solo da mostrare; il form usa i campi salvati. */
  effective_range_area?: string
  effective_components?: string
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
  /** Incantesimo di cura: «Lancia» apre il tiro di cura (lo decide il server). */
  is_healing?: boolean
  higher_levels_dice?: string | null
  /** Seconda parte del danno, di un altro tipo (Colpo infuocato: fuoco e radioso). */
  extra_damage_dice?: string | null
  extra_damage_type?: string | null
  class_id?: number | null
  always_prepared?: boolean
  /** Libro del Mago: l'incantesimo è nel libro, nella copia di riserva, ed è di un libro (livello 1+ di un mago 2014). */
  in_spellbook?: boolean
  in_backup?: boolean
  has_book?: boolean
  /** CD e attacco della classe dell'incantesimo. */
  save_dc?: number | null
  attack_bonus?: number | null
  /** Un privilegio lo concede a volontà: si lancia senza slot (Mille Forme). */
  at_will?: boolean
  /** Si lancia anche coi punti ki (Arti dell'Ombra, discipline dei Quattro Elementi): costo base, ki in più ammessi, ki rimasti. */
  ki_cast?: { cost: number; max_extra: number; ki_left: number; feature_key: string; self_only?: boolean } | null
  /** Lancio pagato da un privilegio del Warlock: Arcanum Mistico (senza slot) o una supplica a uso singolo (slot di Patto). */
  /** Condizioni che il lancio può togliere nell'edizione di chi lancia (Task 48). */
  removal?: RemovalInfo | null
  /** Effetto dell'incantesimo nel catalogo (edizione di chi lancia): chi può riceverlo, quanti per livello di slot, le scelte. */
  effect?: SpellEffectInfo | null
  pact_cast?: { kind: 'arcanum' | 'invocation'; feature_key: string; pact_only: boolean; uses_left: number | null; also_slot?: boolean } | null
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
  container_id?: number | null
  /** Solo per i contenitori, nelle risposte CharacterFull. */
  container_stats?: ContainerStats | null
  /** Proprietà di maestria 2024 dell'arma: si mostra solo ai personaggi 2024. */
  /** Arti Marziali vale per quest'arma (Destrezza e dado da monaco): lo calcola il server sulla scheda. */
  martial_arts?: boolean
  mastery?: string
  /** Portata in più nel proprio turno, da un privilegio (Radici Percuotenti). */
  reach_bonus_ft?: number | null
  /** Effetto di catalogo di ogni incantesimo concesso (stesso ordine di `granted_spells`); `null` se non ne ha. */
  granted_effects?: (SpellEffectInfo | null)[] | null
}

export interface ContainerStats {
  contents_weight: number
  items_count: number
  containers_count: number
  over_capacity: boolean
}

export type CoinKey = 'copper' | 'silver' | 'electrum' | 'gold' | 'platinum'

export interface ContainerMeta {
  capacity_lb: number | null
  counts_weight: boolean
  quick_access: boolean
  coins: Partial<Record<CoinKey, number>>
}

export interface CoinLocation {
  container_id: number | null
  name: string | null
  coins: Partial<Record<CoinKey, number>>
}

export interface CurrencyOpResult {
  coin_totals: Record<CoinKey, number>
  purse: Record<string, number>
  placements: { container_id: number | null; amount: number }[]
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
  classes?: { class_name: string; level: number; subclass?: string | null }[]
  heroic_inspiration: boolean
  /** 2024: ricevuta un'altra Ispirazione avendone già una: da cedere. */
  inspiration_extra?: boolean
  /** 2024: CD per trovare il personaggio nascosto. */
  hiding_dc?: number | null
  experience_points: number
  hp_max_homebrew_modifier: number
  hp_max_effective?: number | null
  ac_homebrew_modifier: number
  ac_items_modifier?: number
  is_dead: boolean
}

export interface ConcentrationSaveResult {
  notes?: string[]
  auto_fail?: boolean
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
  /** Già compreso in `ac`: privilegi, scudo senza addestramento 2024. */
  rules?: number
}

/** Valori derivati dalle regole (condizioni, privilegi) sommati a homebrew e oggetti. */
export interface ComputedStats {
  speed: number
  hp_max_effective: number
  resistances: string[]
  immunities: string[]
  vulnerabilities?: string[]
  incapacitated: boolean
  surprised?: boolean
  /** Da sorpreso (2014): i privilegi il cui «Usa» permette di agire, Ira per l'Istinto Ferino. */
  surprise_exit_features?: string[]
  save_flat: Record<string, number>
  /** Volo pari alla velocità a terra, da un privilegio (Aquila in ira). */
  fly_speed?: number | null
  /** Scalare e nuotare pari alla velocità a terra, da un privilegio (Pantera, Salmone). */
  climb_speed?: number | null
  swim_speed?: number | null
  /** Sensi dati da un privilegio (Percezione Cieca): la scheda mostra il maggiore fra questi e i suoi. */
  senses?: { type: string; range_ft: number }[]
  /** Piedi in più al salto in lungo con rincorsa (Lavoro al Secondo Piano); assente senza il privilegio. */
  long_jump_bonus_ft?: number | null
  /** Sintonie ammesse: 3, o 4 con Usare Dispositivi Magici (Furfante 2024). */
  attunement_limit?: number
  /** Può lanciare dalle pergamene (Usare Dispositivi Magici). */
  scroll_casting?: boolean
}

/** Blocco derivato dal BE: preparazione incantesimi + capacità rituali. */
export interface SpellcastingInfo {
  has_preparing_class: boolean
  prepared_cap: number | null
  prepared_count: number
  cap_mode: 'auto' | 'manual'
  has_ritual_caster: boolean
  /** Incantesimi concessi da un privilegio come soli rituali (Cercatore di Spiriti). */
  ritual_only_spell_ids?: number[]
  has_wizard: boolean
  casters: { class_id: number; class_name: string; ability: string; save_dc: number; attack_bonus: number }[]
  /** Limiti per classe; `null`: quel limite non vale per la classe. */
  limits?: {
    class_id: number
    class_name: string
    cantrips_count: number
    cantrips_limit: number | null
    known_count: number
    known_limit: number | null
    prepared_count: number
    prepared_limit: number | null
    /** Cavaliere Mistico: scuole ammesse, quanti conosciuti possono essere di altre scuole e quanti lo sono. */
    school_names?: string[] | null
    school_free_limit?: number | null
    school_outside_count?: number
  }[]
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
  computed?: ComputedStats
  coin_totals?: Record<CoinKey, number>
  coin_breakdown?: CoinLocation[]
  unequipped_item_names?: string[]
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
  unarmored_formula?: string[] | null
  /** CA senza armatura con la seconda caratteristica scelta, per l'anteprima (dal server). */
  unarmored_previews?: Record<string, number>
  /** Dadi di danno del colpo senz'armi adesso, Arti Marziali compresa (dal server). */
  unarmed_damage_dice?: string
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
  rules_edition: '2014' | '2024'
  spellcasting?: SpellcastingInfo | null
  concentrating_spell_id?: number
  active_states?: ActiveState[] | null
  hp_gained?: number
  /** Scelte di livello in sospeso (aumento caratteristiche / talento). */
  pending_choices?: PendingChoice[] | null
  concentration_save?: ConcentrationSaveResult | null
  /** Solo da PATCH /hp (danno): il danno subito dopo resistenze e vulnerabilità. */
  damage_taken?: number | null
  /** Solo da PATCH /hp: il danno che un incantesimo (Legame di Protezione) ha girato al lanciatore e il suo TS di concentrazione. */
  shared_damage?: { amount: number; caster_name: string; concentration_save?: ConcentrationSaveResult | null } | null
  /** TS automatico a 0 PF di un privilegio (Ira Implacabile): se riesce resta in piedi. */
  zero_hp_save?: ZeroHpSaveResult | null
  /** Id dello snapshot per annullare l'ultima modifica PF; null se nulla è cambiato. */
  hp_undo_id?: string | null
  /** Solo da PATCH /hp dopo un danno: le reazioni che il danno ha aperto (Ritorsione). */
  reactions?: RollOption[] | null
  homebrew_notifications?: Array<Record<string, unknown>> | null
  /** Solo dal riposo con Resilienza Celestiale: chi ha ricevuto PF temporanei. */
  temp_received?: { name: string; given: number; temp_hp: number; applied: boolean }[]
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
  option_result?: OptionResult
  /** Lanciato, ma i dadi di danno dell'incantesimo non sono tirabili dal server. */
  damage_unrollable?: boolean
  /** POST /spells/{id}/use: esiti delle condizioni tolte, nelle due lingue (Task 48). */
  removal_result?: { it: string; en: string }[]
  /** POST /spells/{id}/use|attack e /items/{id}/cast: chi ha ricevuto l'effetto dell'incantesimo. */
  spell_effects?: SpellEffectsResult
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
  campaign_id?: number | null
  campaign_name?: string | null
}

export interface NoteCampaign {
  id: number
  name: string
  current: boolean
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
  character_name?: string | null
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
  /** Solo da GET /sessions/me: stato dell'incontro aperto, se c'è. */
  encounter_status?: 'setup' | 'active' | null
  campaign_id?: number | null
  campaign_name?: string | null
}

export type CampaignMemberStatus = 'active' | 'reserve' | 'dead'

export interface CampaignRead {
  id: number
  name: string
  invite_code?: string | null
  is_gm: boolean
}

export interface CampaignSummary {
  id: number
  name: string
  is_gm: boolean
  member_count: number
  last_session_at?: string | null
  active_session_id?: number | null
}

export interface CampaignMember {
  character_id: number
  character_name: string
  class_summary: string
  total_level: number
  user_id: number
  player_name?: string | null
  status: CampaignMemberStatus
  is_mine: boolean
}

export interface CampaignStash {
  items: Item[]
  currency: Currency
}

export interface CampaignSessionEntry {
  id: number
  created_at: string
  duration_seconds: number
  number: number
  has_recap: boolean
}

export interface SessionRecapCharacter {
  character_id: number
  name: string
  player_name: string | null
  class_summary: string
  level: number
  dice: { rolls: number; nat20: number; nat1: number; highest: number | null }
  damage_taken: number
  healed: number
  downed: number
  death_saves: { successes: number; failures: number }
  spells_cast: number
  slots_used: Record<string, number>
  rests: { short: number; long: number }
  conditions: string[]
}

export interface SessionRecap {
  version: number
  session_id: number
  campaign_id: number | null
  campaign_name: string | null
  number: number | null
  started_at: string
  ended_at: string
  duration_seconds: number
  characters: SessionRecapCharacter[]
  combat: { encounters: number; rounds: number; monsters: string[] }
  items: {
    gm_grants: { to: string | null; item: string; quantity: number }[]
    trades: { from: string; to: string; summary: string }[]
    stash: { kind: 'stash_put' | 'stash_take' | 'gm_stash_add' | 'gm_stash_remove'; who: string | null; summary: string }[]
  }
  lore: { id: number; title: string }[]
  /** Assente nei recap vecchi. */
  places?: { map_id: number; marker_id: number | null; title: string }[]
  highlights: { key: 'unluckiest' | 'luckiest' | 'most_damage' | 'top_healer'; character_id: number; name: string; value: number }[]
}

export interface ScheduleRead {
  /** ISO UTC senza suffisso Z. */
  starts_at: string
  id: number
  note: string | null
  session_id: number | null
  status: 'planned' | 'done' | 'skipped'
}

export interface CampaignDetail {
  id: number
  name: string
  invite_code?: string | null
  is_gm: boolean
  gm_user_id: number
  active_session_id?: number | null
  members: CampaignMember[]
  stash: CampaignStash
  sessions: CampaignSessionEntry[]
  my_last_character_id?: number | null
}

export interface ActiveCampaignSession {
  campaign_id: number
  campaign_name: string
  session_id: number
  my_last_character_id?: number | null
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
  condition_effects?: ConditionEffect[]
  has_pending_save?: boolean
  is_concentrating?: boolean
  /** Stati con effetti su altri (Lupo, Orso, Attacco Irruento): li vedono tutti i partecipanti. */
  active_states?: PublicState[]
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
  /** Colto di sorpresa nel primo turno (lo segna il GM). */
  surprised?: boolean
  conditions: Record<string, unknown>
  current_hp: number | null
  max_hp: number | null
  ac: number | null
  hp_bucket: HpBucket | null
  condition_effects?: ConditionEffect[]
  pending_saves?: PendingSave[]
  /** PG: stati attivi con effetti su altri (Lupo, Orso, Attacco Irruento), per il GM e il gruppo. */
  active_states?: PublicState[]
}

export interface PublicState {
  key: string
  name: string
  rounds_left: number | null
  others: { key: string; name: string; text: string }[]
}

export interface GmConditionApply {
  slug: string
  value?: boolean | number | Record<string, unknown>
  expiry?: { anchor: 'owner' | 'source'; edge: 'start' | 'end'; count: number }
  save?: { ability: string; dc: number; edge: 'start' | 'end' }
  source_combatant_id?: number
  ends_with_concentration?: boolean
}

export interface EncounterLive {
  /** Solo in risposta al tiro di iniziativa. */
  initiative_roll?: { mode_applied: 'normal' | 'advantage' | 'disadvantage'; notes: string[]; option_result?: OptionResult } | null
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
  surprised?: boolean
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

export interface RollDamageRequest extends Partial<RollChoice> {
  casting_level?: number
  extra_dice?: string
  is_critical?: boolean
  main_rolls?: number[]
  extra_rolls?: number[]
  /** Tipo della seconda parte, se l'incantesimo ne offre più d'uno (radioso o necrotico). */
  extra_damage_type?: string
  /** Tipo di danno scelto al lancio (Sfera Cromatica...); il server lo riconvalida. */
  damage_type?: string
}

export interface RollHealingRequest extends Partial<RollChoice> {
  casting_level?: number
  apply_to_self?: boolean
}

/** Esito di POST /characters/{id}/spells/{spell_id}/roll_healing (R41). */
export interface RollHealingResult {
  option_result?: OptionResult
  rolls: number[]
  total: number
  breakdown: string
  casting_level: number
  main_kind: string | null
  main_rolls: number[]
  modifier: number
  bonus: number
  maximized: boolean
  healed: number
  self_healed: number
}

/** Esito di POST /characters/{id}/spells/{spell_id}/attack. */
export interface SpellAttackResult {
  notes?: string[]
  forced_hit?: boolean
  spell_name: string
  to_hit_die: number
  dice?: number[]
  mode?: 'normal' | 'advantage' | 'disadvantage'
  to_hit_bonus: number
  to_hit_total: number
  is_critical: boolean
  is_fumble: boolean
  caster_class: string | null
  cast_option_result?: OptionResult
  /** Incantesimo Raddoppiato: il tiro per colpire del secondo bersaglio. */
  twinned_attack?: { die: number; dice: number[]; mode: string; total: number; is_critical: boolean; is_fumble: boolean }
  character: CharacterFull
  homebrew_notifications?: Array<Record<string, unknown>> | null
}

export interface SpellAttackRequest extends Partial<RollChoice> {
  slot_id?: number
  slot_level: number | null
  confirm?: string[]
  cast_options?: string[]
  cast_option_inputs?: RollChoice['option_inputs']
  ritual?: boolean
  die?: number
  dice?: number[]
  mode?: 'normal' | 'advantage' | 'disadvantage'
  with_inspiration?: boolean
}

export interface RollDamageResult {
  /** Trucchetto Potente: il danno di chi supera il TS contro un trucchetto di danno. */
  save_success_damage?: number | null
  option_result?: OptionResult
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
  /** Tipo della seconda parte di danno dell'incantesimo, se c'è. */
  extra_damage_type?: string | null
  /** I gruppi di dadi, ciascuno col suo tipo: principale, seconda parte, dadi a mano. */
  parts?: { label: 'main' | 'second' | 'extra'; type: string | null; kind: string; rolls: number[] }[]
  /** `[lati, valore]` dei dadi ritirabili (anche quelli delle opzioni), con l'indice del server. */
  reroll_dice?: [number, number][]
  /** Incantesimo Raddoppiato: i danni del secondo bersaglio di un incantesimo con tiro per colpire. */
  twinned_damage?: { rolls: number[]; total: number }
}

export interface TradeRequest {
  from_character_id: number
  to_user_id: number
  item_id?: number
  quantity?: number
  coins?: Partial<Record<CoinKey, number>>
}

export interface StashMoveRequest {
  item_id?: number
  quantity?: number
  coins?: Partial<Record<CoinKey, number>>
}

export interface TradeSnapshot {
  name: string
  quantity: number
  coins: Record<string, number> | null
  children: TradeSnapshot[]
}

export interface LoreRead {
  id: number
  title: string
  body: string
  tags: string[]
  has_image: boolean
  has_audio: boolean
  revealed: boolean
  revealed_at: string | null
  created_at: string
  updated_at: string
}

export type TradeKind = 'trade' | 'stash_put' | 'stash_take' | 'gm_stash_add' | 'gm_stash_remove'

export interface TradePayload {
  /** Assente nelle righe vecchie: vale `trade`. Il lato deposito/master ha `character_id: null`. */
  kind?: TradeKind | 'lore_reveal' | 'atlas_reveal'
  /** Solo kind='lore_reveal'. */
  lore_id?: number
  /** Solo kind='atlas_reveal'. */
  map_id?: number
  marker_id?: number | null
  title?: string
  from: { character_id: number | null; name: string }
  to: { character_id: number | null; name: string }
  items: TradeSnapshot[]
  coins: Record<string, number>
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
  // scambio fra PG
  trade?: TradePayload | null
}

export interface SessionFeedResponse {
  items: SessionFeedItem[]
  has_more: boolean
}

export interface TurnBlock {
  action_used: boolean
  bonus_used: boolean
  reaction_used: boolean
  attacks_made: number
  action_attacks: number
  extra_actions: number
  once_per_turn: string[]
  spell_slot_cast: boolean
  bonus_spell_cast: boolean
  free_interaction_used: boolean
  /** Cure ricevute all'inizio di questo turno da un privilegio (Sopravvissuto): quanto e perché. */
  start_heal?: { feature_key: string; name: { it: string; en: string }; amount: number; message?: { it: string; en: string } | null }[]
  /** Livello dell'ultimo incantesimo lanciato con l'azione in questo turno (0: trucchetto). */
  action_spell_level?: number | null
  pending_attack?: Record<string, unknown> | null
  /** Ordini alla bestia del Signore delle Bestie in questo turno: quanti attacchi le restano. */
  beast?: { id: number; attacks_left?: number; attacked?: boolean; bonus_order?: boolean; commands?: string[] }
  last_roll?: { roll_id: string; roll?: string; skill?: string | null; total: number; refundable?: Record<string, string[]> } | null
}

export type TurnSlot = 'action' | 'bonus' | 'reaction' | 'free_interaction' | 'spell_slot' | 'bonus_spell' | 'attack'

export interface TurnState {
  turn: TurnBlock
  attacks_allowed: number
  /** Il limite con l'arma del patto in mano (Lama Assetata). */
  attacks_allowed_pact?: number
  /** Nascondersi 2024: il totale di Furtività che rende Invisibili (regola del server). */
  hide_min_total?: number
  in_encounter: boolean
  is_my_turn: boolean
  round: number | null
  session_id: number | null
  pending_saves?: PendingSave[]
  /** Firma di stati attivi, CA e PF: cambia quando un alleato dà un effetto, e la scheda va riletta. */
  effects_sig?: string
}

export interface ActiveForm {
  companion_id: number
  name: string
  current_hp: number
  max_hp: number
  temp_hp: number
  armor_class: number
  /** 2014: la forma ha PF propri; 2024: i PF sono del druido, con i temporanei. */
  own_hp?: boolean
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
  /** Bonus totali di abilità e TS della creatura (sul druido in Forma Selvatica valgono se più alti dei suoi). */
  skills?: Record<string, number>
  saves?: Record<string, number>
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
  feature_key?: string | null
  /** Compagno di privilegio: si somma al bonus dello statblock. */
  attack_bonus_extra?: number
  damage_bonus_extra?: number
  /** Investitura del Padrone delle Catene: CD del warlock, volo o nuoto in metri, tipi di danno a scelta, resistenza in reazione. */
  save_dc?: number | null
  fly_or_swim_m?: number
  damage_type_options?: string[]
  can_resist?: boolean
  /** Danno alla forma attiva: il TS di concentrazione che il personaggio ha tirato per l'eccesso. */
  concentration_save?: ConcentrationSaveResult | null
}

export type BeastCommand = 'attack' | 'help' | 'disengage' | 'dash' | 'dodge'

export interface HitDiceResult {
  companion: Companion
  rolls: number[]
  healed: number
  hit_dice_left: number
}

/** `spell_school`: l'incantesimo che ha creato l'evocato (Evocazioni Perduranti, Servitori Non Morti del Mago). */
export type CompanionPayload = { spell_school?: 'conjuration' | 'necromancy' | null } & Partial<Pick<Companion,
  'kind' | 'name' | 'srd_index' | 'statblock' | 'max_hp' | 'current_hp' | 'temp_hp' | 'armor_class' | 'notes' | 'is_active' | 'feature_key'>>

export interface CompanionAttackResult {
  notes?: string[]
  to_hit_die: number
  to_hit_bonus: number
  to_hit_total: number
  dice: number[]
  mode: 'normal' | 'advantage' | 'disadvantage'
  is_critical: boolean
  damage_rolls: number[]
  damage_total: number
  damage_type: string | null
  /** Colpo Primordiale: l'attacco in forma bestiale conta come magico per resistenze e immunità. */
  is_magical?: boolean
  option_result?: OptionResult
  /** `[lati, valore]` dei dadi ritirabili, con l'indice del server. */
  reroll_dice?: [number, number][]
}

/** Forma Selvatica da Combattimento: la cura della forma con uno slot. */
export interface WildHealResult {
  companion: Companion
  slot_level: number
  rolls: number[]
  healed: number
}

// Import da D&D Beyond (POST /characters/import/ddb)
export interface DdbReportEntry {
  section: string
  name: string
  reason: string
}

export interface DdbImportReport {
  imported: DdbReportEntry[]
  approximated: DdbReportEntry[]
  skipped: DdbReportEntry[]
}

export interface DdbImportResult {
  character: CharacterFull
  report: DdbImportReport
}

// Campaign atlas (mirror of api/schemas/atlas.py)
export interface AtlasMap {
  id: number
  name: string
  revealed: boolean
  revealed_at: string | null
  updated_at: string
  marker_count: number
}

export interface MarkerType {
  id: number | null
  key: string | null
  name: string
  icon: string
  color: string
  builtin: boolean
  can_delete: boolean
}

export type MarkerVisibility = 'private' | 'public'

export interface AtlasMarker {
  id: number
  map_id: number
  name: string
  description: string
  x: number
  y: number
  visibility: MarkerVisibility
  type: MarkerType
  author_role: 'gm' | 'player'
  author_name: string | null
  mine: boolean
  link_map_id: number | null
  can_edit: boolean
  can_delete: boolean
  updated_at: string
}

export interface AtlasMarkerCreate {
  name: string
  description?: string
  x: number
  y: number
  type_key?: string | null
  custom_type_id?: number | null
  visibility?: MarkerVisibility
  link_map_id?: number | null
}

export type AtlasMarkerUpdate = Partial<Omit<AtlasMarkerCreate, 'visibility'>>

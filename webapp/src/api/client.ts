/**
 * Typed API client for the FastAPI backend.
 *
 * Every request includes X-Telegram-Init-Data for server-side HMAC verification.
 * The base URL is read from VITE_API_BASE_URL (set in .env.local for dev).
 */

import { getDevUserId } from '@/auth/devUser'
import { getInitData } from '@/auth/telegram'
import type {
  HomebrewResource,
  HomebrewRule,
  HomebrewRuleCreate,
  HomebrewRuleUpdate,
  NotificationRead,
  TemplateDetailRead,
  TemplateRead,
} from '@/lib/homebrew/types'
import type {
  Ability,
  CharacterFull,
  TradeRequest,
  StashMoveRequest,
  DdbImportResult,
  ResolveChoiceBody,
  ClassOptionsState,
  CharacterSummary,
  CombatantPatch,
  GmConditionApply,
  ConcentrationSaveResult,
  Currency,
  CoinKey,
  CurrencyOpResult,
  DiceRollResult,
  EncounterLive,
  EncounterMode,
  GameSession,
  CampaignRead,
  CampaignSummary,
  LoreRead,
  AtlasMap,
  AtlasMarker,
  AtlasMarkerCreate,
  AtlasMarkerUpdate,
  MarkerType,
  MarkerVisibility,
  ScheduleRead,
  CampaignDetail,
  CampaignMemberStatus,
  ActiveCampaignSession,
  SessionRecap,
  CampaignStash,
  TurnState,
  TurnBlock,
  TurnSlot,
  ActiveState,
  FeatureUseResult,
  PendingSaveRollResult,
  GameSessionLive,
  HistoryEntry,
  HistoryRetentionPreview,
  Item,
  MapEntry,
  Note,
  NoteCampaign,
  ParticipantIdentity,
  RollDamageRequest,
  RollDamageResult,
  SpellAttackRequest,
  SpellAttackResult,
  Companion,
  CompanionAttackResult,
  CompanionPayload,
  SessionFeedResponse,
  SessionMessage,
  ShareImportResult,
  SharePreview,
  Spell,
  SpellSlot,
} from '@/types'

export type RollMode = 'normal' | 'advantage' | 'disadvantage'

/** Legacy single die (number) or the new `{dice, mode}` pair; omit values and the server rolls. */
export type D20Roll = number | ({ dice?: number[]; mode?: RollMode } & Partial<RollChoice>)

function d20Fields(roll: D20Roll | undefined): Record<string, unknown> {
  return typeof roll === 'object' ? { ...roll } : { die: roll }
}

// Conferma al tiro (GET /characters/{id}/roll-options)
export type RollOptionPhase = 'before' | 'after_hit' | 'damage_in'

export type RollOption = {
  key: string
  phase: RollOptionPhase
  label: string
  source: string
  dice: string | null
  bonus: number | null
  mode: 'advantage' | 'disadvantage' | null
  multiplier: number | null
  once_per_turn: boolean
  slot: string | null
  needs: string | null
  requires_input: 'slot' | null
  input_options: { level: number; available: number; dice: string | null }[]
  auto_fail: boolean
  cost: { feature_key: string | null; amount: number; spell_slot_min: number | null } | null
}

export type RollOptionsQuery = {
  roll: 'attack' | 'spell_damage' | 'skill' | 'save' | 'initiative' | 'damage_taken'
  item_id?: number
  spell_id?: number
  ability?: string
  skill?: string
  damage_type?: string
}

export type RollChoice = {
  options: string[]
  option_inputs: Record<string, { slot_level: number }>
  defer_damage?: boolean
  /** Solo dopo il tiro per colpire: il giocatore dichiara il mancato o ritira con l'ispirazione. */
  outcome?: 'miss' | 'reroll'
}

export type OptionResult = {
  keys: string[]
  extra_rolls: number[]
  extra_total: number
  bonus: number
  multiplier: number
  spent: string[]
  damage_before?: number | null
  damage_after?: number | null
}

export type RollResult = {
  die: number
  dice?: number[]
  mode?: RollMode
  notes?: string[]
  auto_fail?: boolean
  bonus: number
  total: number
  is_critical: boolean
  is_fumble: boolean
  description?: string
  option_result?: OptionResult
}

export type GrantItemPayload = {
  name: string
  description?: string
  weight: number
  quantity: number
  item_type: string
  item_metadata?: Record<string, unknown> | null
  is_equipped?: boolean
}

export type GMGrantItemResult = {
  user_id: number
  character_id: number | null
  item_id: number | null
  status: 'ok' | 'not_a_player' | 'no_character' | 'character_not_found'
}

export type GMGrantItemResponse = {
  results: GMGrantItemResult[]
}

export type WeaponAttackResult = {
  weapon_name: string
  to_hit_die: number
  dice?: number[]
  mode?: RollMode
  notes?: string[]
  to_hit_bonus: number
  to_hit_total: number
  is_critical: boolean
  is_fumble: boolean
  magic_bonus?: number
  proficiency_warning?: boolean
  damage_dice: string
  damage_rolls: number[]
  damage_bonus: number
  damage_total: number
  ammo?: { item_id: number; name: string; remaining: number } | null
  ammo_missing?: boolean
  option_result?: OptionResult
  /** Attacco in sospeso: il danno finale passa da `attackDamage`. */
  attack_id?: string
}

export type HitDiceSpendResult = {
  rolls: number[]
  con_bonus: number
  healed: number
  new_current_hp: number
  homebrew_notifications?: Array<Record<string, unknown>> | null
}

export type RestPreview = {
  hp_gain: number
  hit_dice_regain: Record<string, number>
  slots: Record<string, number>
  pact_slots: number
  abilities: string[]
  homebrew_resources: string[]
  item_charges: { name: string; gain: number | null; formula: string | null; full: boolean }[]
  exhaustion_change: number
  ends_concentration: boolean
}

export type DeathSaveRollResult = {
  die: number
  dice?: number[]
  mode?: RollMode
  notes?: string[]
  outcome: 'nat20' | 'nat1' | 'success' | 'failure'
  successes: number
  failures: number
  stable: boolean
  revived: boolean
  current_hp: number
}

export type DiceResultEntryBody = {
  kind: 'd4' | 'd6' | 'd8' | 'd10' | 'd12' | 'd20'
  value: number
}

export type DiceResultRequestBody = {
  rolls: DiceResultEntryBody[]
  label?: string | null
  modifier?: number
  notation?: string | null
  with_inspiration?: boolean
  total?: number | null
  mode?: RollMode
}

export type { ConcentrationSaveResult } from '@/types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    const detailStr = typeof detail === 'string' ? detail : JSON.stringify(detail)
    super(`API ${status}: ${detailStr}`)
    this.name = 'ApiError'
  }
}

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    'X-Telegram-Init-Data': getInitData(),
  }
  const devUserId = getDevUserId()
  if (devUserId) headers['X-Dev-User-Id'] = devUserId
  return headers
}

// Una richiesta appesa (Wi-Fi del locale, tunnel che cade) lasciava lo spinner
// `pending` per sempre: oltre questa soglia si fallisce e la UI può reagire.
const REQUEST_TIMEOUT_MS = 20_000

function timeoutSignal(): AbortSignal | undefined {
  return typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function'
    ? AbortSignal.timeout(REQUEST_TIMEOUT_MS)
    : undefined
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    signal: options.signal ?? timeoutSignal(),
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...options.headers,
    },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, body.detail ?? res.statusText)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

async function requestFormData<T>(
  path: string,
  formData: FormData,
  method: 'POST' | 'PATCH' | 'PUT' = 'POST',
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: authHeaders(),
    body: formData,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, body.detail ?? res.statusText)
  }
  return res.json() as Promise<T>
}

// XHR-based upload — exposes upload.onprogress for percent UI. Fetch + ReadableStream
// can't observe outbound progress in browsers, so we keep XMLHttpRequest here.
function requestFormDataWithProgress<T>(
  path: string,
  formData: FormData,
  onProgress: (pct: number) => void,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${BASE_URL}${path}`)
    for (const [name, value] of Object.entries(authHeaders())) {
      xhr.setRequestHeader(name, value)
    }
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100))
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as T)
        } catch {
          reject(new ApiError(xhr.status, 'Invalid JSON response'))
        }
      } else {
        let detail = xhr.statusText
        try {
          detail = (JSON.parse(xhr.responseText) as { detail?: string }).detail ?? detail
        } catch {
          /* keep statusText */
        }
        reject(new ApiError(xhr.status, detail))
      }
    }
    xhr.onerror = () => reject(new ApiError(0, 'Network error'))
    xhr.onabort = () => reject(new ApiError(0, 'Upload aborted'))
    xhr.send(formData)
  })
}

// ---------------------------------------------------------------------------
// Characters
// ---------------------------------------------------------------------------

function attackBody(
  withInspiration: boolean,
  roll: D20Roll | undefined,
  choice?: { grip?: 'one' | 'two'; attack_mode?: 'melee' | 'thrown' },
): string | undefined {
  const fields = roll === undefined ? {} : d20Fields(roll)
  if (!withInspiration && roll === undefined && !choice) return undefined
  return JSON.stringify({
    ...(withInspiration ? { with_inspiration: true } : {}),
    ...fields,
    ...choice,
  })
}

export const api = {
  health: () => request<{ status: string; version: string | null }>('/health'),

  me: () => request<{ user_id: number }>('/auth/me'),

  characters: {
    list: () => request<CharacterSummary[]>('/characters'),
    get: (id: number) => request<CharacterFull>(`/characters/${id}`),
    create: (
      name: string,
      initialClass?: {
        class_name: string
        level?: number
        hit_die?: number
        spellcasting_ability?: string | null
        skill_choices?: string[]
      } | null,
      identity?: {
        race?: string
        gender?: string
        alignment?: string
        background?: string
        languages?: string[]
        personality?: { traits: string }
      } | null,
      extras?: {
        ability_scores?: Record<string, number>
        species?: object
        skills?: Record<string, boolean>
      },
    ) =>
      request<CharacterFull>('/characters', {
        method: 'POST',
        body: JSON.stringify({
          name,
          ...(initialClass ? { initial_class: initialClass } : {}),
          ...(identity ? { identity } : {}),
          ...extras,
        }),
      }),
    update: (id: number, data: Record<string, unknown>) =>
      request<CharacterFull>(`/characters/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      request<void>(`/characters/${id}`, { method: 'DELETE' }),

    // Export / import / duplicate
    export: (id: number) => request<unknown>(`/characters/${id}/export`),
    exportSend: (id: number) =>
      request<{ ok: boolean }>(`/characters/${id}/export/send`, { method: 'POST' }),
    import: (file: File) => {
      const fd = new FormData()
      fd.append('file', file)
      return requestFormData<CharacterFull>('/characters/import', fd)
    },
    duplicate: (id: number) =>
      request<CharacterFull>(`/characters/${id}/duplicate`, { method: 'POST' }),
    importDdb: (url: string) =>
      request<DdbImportResult>('/characters/import/ddb', {
        method: 'POST',
        body: JSON.stringify({ url }),
      }),

    // HP
    updateHp: (
      id: number,
      op: string,
      value: number,
      wasCritical = false,
      modifier?: { damage_modifier?: 'half' | 'double' | 'none' | 'immune'; raw_value?: number; damage_type?: string } & Partial<RollChoice>,
    ) =>
      request<CharacterFull>(`/characters/${id}/hp`, {
        method: 'PATCH',
        body: JSON.stringify({ op, value, was_critical_hit: wasCritical, ...modifier }),
      }),
    undoHp: (id: number, opId: string) =>
      request<CharacterFull>(`/characters/${id}/hp/undo`, {
        method: 'POST',
        body: JSON.stringify({ op_id: opId }),
      }),
    revive: (id: number) =>
      request<CharacterFull>(`/characters/${id}/revive`, {
        method: 'POST',
      }),
    rest: (
      id: number,
      restType: 'long' | 'short',
      opts?: { interrupted?: boolean; ate_and_drank?: boolean; confirm_early?: boolean },
    ) =>
      request<CharacterFull>(`/characters/${id}/rest`, {
        method: 'POST',
        body: JSON.stringify({ rest_type: restType, ...opts }),
      }),
    restPreview: (id: number, restType: 'long' | 'short') =>
      request<RestPreview>(`/characters/${id}/rest/preview?rest_type=${restType}`),
    updateDeathSaves: (id: number, action: string) =>
      request<CharacterFull>(`/characters/${id}/death_saves`, {
        method: 'PATCH',
        body: JSON.stringify({ action }),
      }),

    // Stats
    updateAbilityScore: (id: number, ability: string, value: number) =>
      request<CharacterFull>(`/characters/${id}/ability_scores/${ability}`, {
        method: 'PATCH',
        body: JSON.stringify({ value }),
      }),
    updateAC: (id: number, data: { base?: number; shield?: number; magic?: number }) =>
      request<CharacterFull>(`/characters/${id}/ac`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    resetACOverride: (id: number) =>
      request<CharacterFull>(`/characters/${id}/ac/reset-override`, {
        method: 'POST',
      }),
    updateCarryCapacity: (id: number, data: { value: number }) =>
      request<CharacterFull>(`/characters/${id}/carry-capacity`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    resetCarryCapacityOverride: (id: number) =>
      request<CharacterFull>(`/characters/${id}/carry-capacity/reset-override`, {
        method: 'POST',
      }),
    setUnarmoredDefense: (id: number, ability: 'wisdom' | 'constitution' | null) =>
      request<CharacterFull>(`/characters/${id}/ac/unarmored-defense`, {
        method: 'POST',
        body: JSON.stringify({ ability }),
      }),
    updateSkills: (id: number, skills: Record<string, unknown>) =>
      request<CharacterFull>(`/characters/${id}/skills`, {
        method: 'PATCH',
        body: JSON.stringify({ skills }),
      }),
    updateSavingThrows: (id: number, saving_throws: Record<string, boolean>) =>
      request<CharacterFull>(`/characters/${id}/saving_throws`, {
        method: 'PATCH',
        body: JSON.stringify({ saving_throws }),
      }),

    // Combat extras
    updateConditions: (id: number, conditions: Record<string, unknown>, durations?: Record<string, number | null>) =>
      request<CharacterFull>(`/characters/${id}/conditions`, {
        method: 'PATCH',
        body: JSON.stringify(durations ? { conditions, durations } : { conditions }),
      }),
    tickRound: (id: number) =>
      request<CharacterFull>(`/characters/${id}/rounds/tick`, { method: 'POST' }),
    turnState: (id: number) =>
      request<TurnState>(`/characters/${id}/turn-state`),
    turnUse: (id: number, slot: TurnSlot, used: boolean = true) =>
      request<TurnBlock>(`/characters/${id}/turn/use`, { method: 'POST', body: JSON.stringify({ slot, used }) }),
    rollOptions: (id: number, query: RollOptionsQuery) =>
      request<RollOption[]>(
        `/characters/${id}/roll-options?${new URLSearchParams(
          Object.entries(query).filter(([, v]) => v !== undefined && v !== '').map(([k, v]) => [k, String(v)]),
        )}`,
      ),
    featureUse: (id: number, featureKey: string, amount: number = 1) =>
      request<FeatureUseResult>(`/characters/${id}/features/${encodeURIComponent(featureKey)}/use`, {
        method: 'POST', body: JSON.stringify({ amount }),
      }),
    endActiveState: (id: number, key: string) =>
      request<ActiveState[]>(`/characters/${id}/active-states/${encodeURIComponent(key)}`, { method: 'DELETE' }),
    turnNew: (id: number) =>
      request<TurnBlock>(`/characters/${id}/turn/new`, { method: 'POST' }),
    pendingSaves: {
      roll: (id: number, saveId: number, die?: D20Roll, withInspiration: boolean = false) =>
        request<PendingSaveRollResult>(`/characters/${id}/pending-saves/${saveId}/roll`, {
          method: 'POST',
          body: JSON.stringify({ ...d20Fields(die), with_inspiration: withInspiration }),
        }),
      dismiss: (id: number, saveId: number) =>
        request<void>(`/characters/${id}/pending-saves/${saveId}/dismiss`, { method: 'POST' }),
    },
    updateInspiration: (id: number, heroic_inspiration: boolean) =>
      request<CharacterFull>(`/characters/${id}/inspiration`, {
        method: 'PATCH',
        body: JSON.stringify({ heroic_inspiration }),
      }),
    updateXP: (id: number, data: { add?: number; set?: number; hp_rolls?: number[] }) =>
      request<CharacterFull>(`/characters/${id}/xp`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),

    // Roll endpoints
    rollSkill: (
      id: number,
      skillName: string,
      die?: D20Roll,
      withInspiration: boolean = false,
    ) =>
      request<RollResult>(`/characters/${id}/skills/${encodeURIComponent(skillName)}/roll`, {
        method: 'POST',
        body:
          die != null || withInspiration
            ? JSON.stringify({ ...d20Fields(die), with_inspiration: withInspiration })
            : undefined,
      }),
    rollSavingThrow: (
      id: number,
      ability: string,
      die?: D20Roll,
      withInspiration: boolean = false,
    ) =>
      request<RollResult>(`/characters/${id}/saving_throws/${encodeURIComponent(ability)}/roll`, {
        method: 'POST',
        body:
          die != null || withInspiration
            ? JSON.stringify({ ...d20Fields(die), with_inspiration: withInspiration })
            : undefined,
      }),

    // Hit dice spending
    spendHitDice: (id: number, classId: number, count: number, rolls?: number[]) =>
      request<HitDiceSpendResult>(`/characters/${id}/hit_dice/spend`, {
        method: 'POST',
        body: JSON.stringify(rolls ? { class_id: classId, count, rolls } : { class_id: classId, count }),
      }),

    // Death save roll
    rollDeathSave: (id: number, die?: D20Roll) =>
      request<DeathSaveRollResult>(`/characters/${id}/death_saves/roll`, {
        method: 'POST',
        body: die != null ? JSON.stringify(d20Fields(die)) : undefined,
      }),

    // HP recalc
    recalcHp: (id: number) =>
      request<CharacterFull>(`/characters/${id}/hp/recalc`, {
        method: 'POST',
      }),
  },

  rules: {
    subclasses: (edition: string, classKey: string) =>
      request<{ key: string; name: Record<string, string>; choice_level: number }[]>(
        `/rules/subclasses?edition=${edition}&class_key=${classKey}`,
      ),
    proficiencies: (edition: string, classKey: string, asMulticlass: boolean) =>
      request<{
        armor: string[]
        weapons: string[]
        tools: string[]
        saves: string[]
        skills_from: string[]
        skills_count: number
        languages: string[]
      }>(`/rules/proficiencies?edition=${edition}&class_key=${encodeURIComponent(classKey)}&as_multiclass=${asMulticlass}`),
  },

  // ---------------------------------------------------------------------------
  // Classes
  // ---------------------------------------------------------------------------
  classes: {
    add: (charId: number, data: Record<string, unknown>) =>
      request<CharacterFull>(`/characters/${charId}/classes`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    update: (charId: number, classId: number, data: Record<string, unknown>) =>
      request<CharacterFull>(`/characters/${charId}/classes/${classId}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    remove: (charId: number, classId: number) =>
      request<CharacterFull>(`/characters/${charId}/classes/${classId}`, {
        method: 'DELETE',
      }),
    distribute: (charId: number, classes: { class_id: number; level: number }[], hpRolls?: number[]) =>
      request<CharacterFull>(`/characters/${charId}/classes/distribute`, {
        method: 'PATCH',
        body: JSON.stringify(hpRolls ? { classes, hp_rolls: hpRolls } : { classes }),
      }),
  },

  // ---------------------------------------------------------------------------
  // Spells
  // ---------------------------------------------------------------------------
  spells: {
    list: (charId: number, q?: string) =>
      request<Spell[]>(`/characters/${charId}/spells${q ? `?q=${encodeURIComponent(q)}` : ''}`),
    add: (charId: number, data: Partial<Spell>) =>
      request<Spell>(`/characters/${charId}/spells`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    update: (charId: number, spellId: number, data: Partial<Spell>) =>
      request<Spell>(`/characters/${charId}/spells/${spellId}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    remove: (charId: number, spellId: number) =>
      request<void>(`/characters/${charId}/spells/${spellId}`, { method: 'DELETE' }),
    use: (charId: number, spellId: number, slotLevel: number | null, asRitual = false) =>
      request<CharacterFull>(`/characters/${charId}/spells/${spellId}/use`, {
        method: 'POST',
        body: JSON.stringify({ slot_level: slotLevel, as_ritual: asRitual }),
      }),
    updateConcentration: (charId: number, spellId: number | null) =>
      request<CharacterFull>(`/characters/${charId}/concentration`, {
        method: 'PATCH',
        body: JSON.stringify({ spell_id: spellId }),
      }),
    concentrationSave: (charId: number, damage: number) =>
      request<ConcentrationSaveResult>(`/characters/${charId}/concentration/save`, {
        method: 'POST',
        body: JSON.stringify({ damage }),
      }),
    rollDamage: (charId: number, spellId: number, body: RollDamageRequest): Promise<RollDamageResult> =>
      request<RollDamageResult>(`/characters/${charId}/spells/${spellId}/roll_damage`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    attack: (charId: number, spellId: number, body: SpellAttackRequest): Promise<SpellAttackResult> =>
      request<SpellAttackResult>(`/characters/${charId}/spells/${spellId}/attack`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
  },

  // ---------------------------------------------------------------------------
  // Spell Slots
  // ---------------------------------------------------------------------------
  spellSlots: {
    add: (charId: number, level: number, total: number) =>
      request<SpellSlot>(`/characters/${charId}/spell_slots`, {
        method: 'POST',
        body: JSON.stringify({ level, total, used: 0 }),
      }),
    update: (charId: number, slotId: number, data: { total?: number; used?: number }) =>
      request<SpellSlot>(`/characters/${charId}/spell_slots/${slotId}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    remove: (charId: number, slotId: number) =>
      request<void>(`/characters/${charId}/spell_slots/${slotId}`, { method: 'DELETE' }),
    resetAll: (charId: number) =>
      request<CharacterFull>(`/characters/${charId}/spell_slots/reset`, { method: 'POST' }),
  },

  // ---------------------------------------------------------------------------
  // Items
  // ---------------------------------------------------------------------------
  items: {
    list: (charId: number) => request<Item[]>(`/characters/${charId}/items`),
    add: (charId: number, data: Partial<Item>) =>
      request<CharacterFull>(`/characters/${charId}/items`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    update: (charId: number, itemId: number, data: Partial<Item>) =>
      request<CharacterFull>(`/characters/${charId}/items/${itemId}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    remove: (charId: number, itemId: number) =>
      request<CharacterFull>(`/characters/${charId}/items/${itemId}`, { method: 'DELETE' }),
    charges: (charId: number, itemId: number, delta: number) =>
      request<CharacterFull>(`/characters/${charId}/items/${itemId}/charges`, {
        method: 'POST',
        body: JSON.stringify({ delta }),
      }),
    cast: (charId: number, itemId: number, spellIndex: number) =>
      request<CharacterFull>(`/characters/${charId}/items/${itemId}/cast`, {
        method: 'POST',
        body: JSON.stringify({ spell_index: spellIndex }),
      }),
    attack: (
      charId: number, itemId: number, withInspiration: boolean = false, die?: D20Roll,
      choice?: { grip?: 'one' | 'two'; attack_mode?: 'melee' | 'thrown' },
    ) =>
      request<WeaponAttackResult>(`/characters/${charId}/items/${itemId}/attack`, {
        method: 'POST',
        body: attackBody(withInspiration, die, choice),
      }),
    attackDamage: (charId: number, attackId: string, choice: RollChoice) =>
      request<WeaponAttackResult>(`/characters/${charId}/attack/${attackId}/damage`, {
        method: 'POST',
        body: JSON.stringify({ options: choice.options, option_inputs: choice.option_inputs }),
      }),
    attackUnarmed: (charId: number, withInspiration: boolean = false, die?: D20Roll) =>
      request<WeaponAttackResult>(`/characters/${charId}/attack/unarmed`, {
        method: 'POST',
        body: attackBody(withInspiration, die),
      }),
    use: (charId: number, itemId: number) =>
      request<CharacterFull>(`/characters/${charId}/items/${itemId}/use`, {
        method: 'POST',
      }),
    move: (charId: number, body: { item_ids: number[]; container_id: number | null; quantity?: number }) =>
      request<CharacterFull>(`/characters/${charId}/items/move`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
  },

  // ---------------------------------------------------------------------------
  // Currency
  // ---------------------------------------------------------------------------
  currency: {
    get: (charId: number) => request<Currency>(`/characters/${charId}/currency`),
    update: (charId: number, data: Partial<Currency>) =>
      request<Currency>(`/characters/${charId}/currency`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    convert: (charId: number, source: string, target: string, amount: number) =>
      request<Currency>(`/characters/${charId}/currency/convert`, {
        method: 'POST',
        body: JSON.stringify({ source, target, amount }),
      }),
    adjust: (
      charId: number,
      body: { coin: CoinKey; delta: number; placements?: { container_id: number | null; amount: number }[] },
    ) =>
      request<CurrencyOpResult>(`/characters/${charId}/currency/adjust`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    move: (
      charId: number,
      body: { coin: CoinKey; amount: number; from_container_id: number | null; to_container_id: number | null },
    ) =>
      request<CurrencyOpResult>(`/characters/${charId}/currency/move`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
  },

  // ---------------------------------------------------------------------------
  // Abilities (features)
  // ---------------------------------------------------------------------------
  companions: {
    list: (charId: number) => request<Companion[]>(`/characters/${charId}/companions`),
    create: (charId: number, body: CompanionPayload) =>
      request<Companion>(`/characters/${charId}/companions`, { method: 'POST', body: JSON.stringify(body) }),
    update: (charId: number, id: number, body: CompanionPayload) =>
      request<Companion>(`/characters/${charId}/companions/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    remove: (charId: number, id: number) =>
      request<void>(`/characters/${charId}/companions/${id}`, { method: 'DELETE' }),
    hp: (charId: number, id: number, op: 'damage' | 'heal' | 'set_temp', value: number) =>
      request<Companion>(`/characters/${charId}/companions/${id}/hp`, { method: 'PATCH', body: JSON.stringify({ op, value }) }),
    attack: (charId: number, id: number, actionIndex: number, mode: RollMode, dice?: number[]) =>
      request<CompanionAttackResult>(`/characters/${charId}/companions/${id}/attack`, {
        method: 'POST', body: JSON.stringify({ action_index: actionIndex, mode, dice }),
      }),
    activate: (charId: number, id: number, force = false) =>
      request<Companion>(`/characters/${charId}/companions/${id}/activate`, { method: 'POST', body: JSON.stringify({ force }) }),
    deactivate: (charId: number, id: number) =>
      request<Companion>(`/characters/${charId}/companions/${id}/deactivate`, { method: 'POST' }),
  },

  abilities: {
    list: (charId: number) => request<Ability[]>(`/characters/${charId}/abilities`),
    add: (charId: number, data: Partial<Ability>) =>
      request<Ability>(`/characters/${charId}/abilities`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    update: (charId: number, abilityId: number, data: Partial<Ability>) =>
      request<Ability>(`/characters/${charId}/abilities/${abilityId}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    remove: (charId: number, abilityId: number) =>
      request<void>(`/characters/${charId}/abilities/${abilityId}`, { method: 'DELETE' }),
  },

  choices: {
    resolve: (charId: number, choiceId: string, body: ResolveChoiceBody) =>
      request<CharacterFull>(`/characters/${charId}/choices/${choiceId}/resolve`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    classOptions: (charId: number, classId: number, group: string) =>
      request<ClassOptionsState>(`/characters/${charId}/classes/${classId}/options/${group}`),
    replaceOption: (charId: number, classId: number, body: { group: string; old_key: string; new_key: string }) =>
      request<CharacterFull>(`/characters/${charId}/classes/${classId}/options/replace`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    removeFeat: (charId: number, abilityId: number) =>
      request<CharacterFull>(`/characters/${charId}/feats/${abilityId}`, { method: 'DELETE' }),
    removeFeatByRule: (charId: number, ruleId: number) =>
      request<CharacterFull>(`/characters/${charId}/feats/by-rule/${ruleId}`, { method: 'DELETE' }),
  },

  // ---------------------------------------------------------------------------
  // Homebrew (rules CRUD + templates + resources + dispatch)
  // ---------------------------------------------------------------------------
  homebrew: {
    listRules: (charId: number) =>
      request<HomebrewRule[]>(`/characters/${charId}/homebrew/rules`),
    getRule: (charId: number, ruleId: number) =>
      request<HomebrewRule>(`/characters/${charId}/homebrew/rules/${ruleId}`),
    createRule: (charId: number, body: HomebrewRuleCreate) =>
      request<HomebrewRule>(`/characters/${charId}/homebrew/rules`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    updateRule: (charId: number, ruleId: number, body: HomebrewRuleUpdate) =>
      request<HomebrewRule>(`/characters/${charId}/homebrew/rules/${ruleId}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    deleteRule: (charId: number, ruleId: number) =>
      request<void>(`/characters/${charId}/homebrew/rules/${ruleId}`, {
        method: 'DELETE',
      }),
    toggleEnabled: (charId: number, ruleId: number, enabled: boolean) =>
      request<HomebrewRule>(`/characters/${charId}/homebrew/rules/${ruleId}/enable`, {
        method: 'POST',
        body: JSON.stringify({ enabled }),
      }),
    listTemplates: () => request<TemplateRead[]>('/homebrew/templates'),
    getTemplate: (id: string) =>
      request<TemplateDetailRead>(`/homebrew/templates/${id}`),
    installTemplate: (charId: number, templateId: string) =>
      request<HomebrewRule>(
        `/characters/${charId}/homebrew/templates/${templateId}/install`,
        { method: 'POST' },
      ),
    listResources: (charId: number) =>
      request<HomebrewResource[]>(`/characters/${charId}/homebrew/resources`),
    patchResource: (charId: number, resourceId: number, current: number) =>
      request<HomebrewResource>(
        `/characters/${charId}/homebrew/resources/${resourceId}`,
        {
          method: 'PATCH',
          body: JSON.stringify({ current }),
        },
      ),
    turnStart: (charId: number) =>
      request<{ notifications: NotificationRead[] }>(
        `/characters/${charId}/homebrew/turn-start`,
        { method: 'POST' },
      ),
    manualTrigger: (charId: number, ruleId: number) =>
      request<{ notifications: NotificationRead[] }>(
        `/characters/${charId}/homebrew/manual-trigger/${ruleId}`,
        { method: 'POST' },
      ),
  },

  // ---------------------------------------------------------------------------
  // Notes
  // ---------------------------------------------------------------------------
  notes: {
    list: (charId: number) => request<Note[]>(`/characters/${charId}/notes`),
    campaigns: (charId: number) => request<NoteCampaign[]>(`/characters/${charId}/notes/campaigns`),
    add: (charId: number, title: string, body: string, tags?: string[], campaignId?: number | null) =>
      request<Note[]>(`/characters/${charId}/notes`, {
        method: 'POST',
        body: JSON.stringify({ title, body, tags: tags ?? [], ...(campaignId != null ? { campaign_id: campaignId } : {}) }),
      }),
    // campaignId: undefined = invariata, null = rimuovi, number = assegna.
    update: (charId: number, title: string, body: string, tags?: string[], campaignId?: number | null) =>
      request<Note[]>(`/characters/${charId}/notes/${encodeURIComponent(title)}`, {
        method: 'PATCH',
        body: JSON.stringify({
          body,
          ...(tags !== undefined ? { tags } : {}),
          ...(campaignId === null ? { clear_campaign: true } : campaignId !== undefined ? { campaign_id: campaignId } : {}),
        }),
      }),
    remove: (charId: number, title: string) =>
      request<Note[]>(`/characters/${charId}/notes/${encodeURIComponent(title)}`, {
        method: 'DELETE',
      }),
    uploadVoice: (charId: number, title: string, audioBlob: Blob, campaignId?: number | null) => {
      const fd = new FormData()
      fd.append('title', title)
      if (campaignId != null) fd.append('campaign_id', String(campaignId))
      fd.append('file', audioBlob, 'voice.webm')
      return requestFormData<Note[]>(`/characters/${charId}/notes/voice`, fd)
    },
    voiceUrl: (charId: number, filename: string) =>
      `${BASE_URL}/characters/${charId}/notes/voice/${encodeURIComponent(filename)}?init_data=${encodeURIComponent(getInitData())}`,
  },

  // ---------------------------------------------------------------------------
  // Maps
  // ---------------------------------------------------------------------------
  maps: {
    list: (charId: number) => request<MapEntry[]>(`/characters/${charId}/maps`),
    fileUrl: (charId: number, mapId: number) =>
      `${BASE_URL}/characters/${charId}/maps/${mapId}/file?init_data=${encodeURIComponent(getInitData())}`,
    remove: (charId: number, mapId: number) =>
      request<void>(`/characters/${charId}/maps/${mapId}`, { method: 'DELETE' }),
    removeZone: (charId: number, zoneName: string) =>
      request<void>(`/characters/${charId}/maps/zone/${encodeURIComponent(zoneName)}`, {
        method: 'DELETE',
      }),
    upload: (charId: number, zoneName: string, file: File) => {
      const fd = new FormData()
      fd.append('zone_name', zoneName)
      fd.append('file', file)
      return requestFormData<MapEntry>(`/characters/${charId}/maps/upload`, fd)
    },
    uploadWithProgress: (
      charId: number,
      zoneName: string,
      file: File,
      onProgress: (pct: number) => void,
    ) => {
      const fd = new FormData()
      fd.append('zone_name', zoneName)
      fd.append('file', file)
      return requestFormDataWithProgress<MapEntry>(
        `/characters/${charId}/maps/upload`,
        fd,
        onProgress,
      )
    },
    reorder: (charId: number, zoneName: string, order: number[]) =>
      request<CharacterFull>(`/characters/${charId}/maps/reorder`, {
        method: 'PATCH',
        body: JSON.stringify({ zone_name: zoneName, order }),
      }),
  },

  // ---------------------------------------------------------------------------
  // Silhouette
  // ---------------------------------------------------------------------------
  silhouette: {
    fileUrl: (charId: number) =>
      `${BASE_URL}/characters/${charId}/silhouette/file?init_data=${encodeURIComponent(getInitData())}`,
    upload: (charId: number, file: File) => {
      const fd = new FormData()
      fd.append('file', file)
      return requestFormData<CharacterFull>(`/characters/${charId}/silhouette`, fd)
    },
    remove: (charId: number) =>
      request<CharacterFull>(`/characters/${charId}/silhouette`, { method: 'DELETE' }),
  },

  // ---------------------------------------------------------------------------
  // Dice
  // ---------------------------------------------------------------------------
  dice: {
    result: (charId: number, body: DiceResultRequestBody) =>
      request<DiceRollResult>(`/characters/${charId}/dice/result`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    /** Iniziativa fuori da un incontro: modo automatico e bonus li decide il server. */
    initiative: (charId: number, roll: D20Roll | undefined, label: string) =>
      request<RollResult>(`/characters/${charId}/dice/initiative`, {
        method: 'POST',
        body: JSON.stringify({ ...d20Fields(roll), label }),
      }),
    history: (charId: number) => request<DiceRollResult[]>(`/characters/${charId}/dice/history`),
    clearHistory: (charId: number) =>
      request<void>(`/characters/${charId}/dice/history`, { method: 'DELETE' }),
    postToChat: (charId: number, result: { notation: string; rolls: number[]; total: number }) =>
      request<{ ok: boolean }>(`/characters/${charId}/dice/post-to-chat`, {
        method: 'POST',
        body: JSON.stringify(result),
      }),
    stats: (charId: number) =>
      request<{ stats: Record<string, Record<string, number>> }>(
        `/characters/${charId}/dice/stats`,
      ),
    resetStats: (charId: number) =>
      request<void>(`/characters/${charId}/dice/stats`, { method: 'DELETE' }),
  },

  // ---------------------------------------------------------------------------
  // Share (prepared messages → Telegram.WebApp.shareMessage)
  // ---------------------------------------------------------------------------
  share: {
    card: (charId: number) =>
      request<{ prepared_message_id: string }>(
        `/characters/${charId}/share/card`, { method: 'POST' }),
    item: (charId: number, itemId: number) =>
      request<{ prepared_message_id: string }>(
        `/characters/${charId}/share/items/${itemId}`, { method: 'POST' }),
    note: (charId: number, title: string) =>
      request<{ prepared_message_id: string }>(
        `/characters/${charId}/share/notes/${encodeURIComponent(title)}`, { method: 'POST' }),
    invite: (sessionId: number) =>
      request<{ prepared_message_id: string }>(
        `/sessions/${sessionId}/share/invite`, { method: 'POST' }),
    recap: (sessionId: number) =>
      request<{ prepared_message_id: string }>(
        `/share/recap/${sessionId}`, { method: 'POST' }),
    campaignInvite: (campaignId: number) =>
      request<{ prepared_message_id: string }>(
        `/share/campaign-invite/${campaignId}`, { method: 'POST' }),
    get: (token: string) => request<SharePreview>(`/shares/${token}`),
    import: (token: string, charId: number) =>
      request<ShareImportResult>(`/shares/${token}/import`, {
        method: 'POST',
        body: JSON.stringify({ char_id: charId }),
      }),
  },

  // ---------------------------------------------------------------------------
  // History
  // ---------------------------------------------------------------------------
  history: {
    get: (charId: number) => request<HistoryEntry[]>(`/characters/${charId}/history`),
    clear: (charId: number) =>
      request<void>(`/characters/${charId}/history`, { method: 'DELETE' }),
    retentionPreview: (charId: number, events: number, days: number) =>
      request<HistoryRetentionPreview>(
        `/characters/${charId}/history/retention-preview?events=${events}&days=${days}`,
      ),
  },

  // ---------------------------------------------------------------------------
  // Campaigns
  // ---------------------------------------------------------------------------
  lore: {
    list: (campId: number) => request<LoreRead[]>(`/campaigns/${campId}/lore`),
    create: (campId: number, fd: FormData) => requestFormData<LoreRead>(`/campaigns/${campId}/lore`, fd),
    update: (campId: number, id: number, fd: FormData) =>
      requestFormData<LoreRead>(`/campaigns/${campId}/lore/${id}`, fd, 'PATCH'),
    remove: (campId: number, id: number) => request<void>(`/campaigns/${campId}/lore/${id}`, { method: 'DELETE' }),
    reveal: (campId: number, id: number) => request<LoreRead>(`/campaigns/${campId}/lore/${id}/reveal`, { method: 'POST' }),
    hide: (campId: number, id: number) => request<LoreRead>(`/campaigns/${campId}/lore/${id}/hide`, { method: 'POST' }),
    // v = updated_at: a replaced file gets a new URL, so the browser cache never shows the old one.
    imageUrl: (campId: number, id: number, v: string) =>
      `${BASE_URL}/campaigns/${campId}/lore/${id}/image?init_data=${encodeURIComponent(getInitData())}&v=${encodeURIComponent(v)}`,
    audioUrl: (campId: number, id: number, v: string) =>
      `${BASE_URL}/campaigns/${campId}/lore/${id}/audio?init_data=${encodeURIComponent(getInitData())}&v=${encodeURIComponent(v)}`,
  },

  atlas: {
    maps: (campId: number) => request<AtlasMap[]>(`/campaigns/${campId}/atlas/maps`),
    uploadMap: (campId: number, fd: FormData) => requestFormData<AtlasMap>(`/campaigns/${campId}/atlas/maps`, fd),
    renameMap: (campId: number, mapId: number, name: string) =>
      request<AtlasMap>(`/campaigns/${campId}/atlas/maps/${mapId}`, { method: 'PATCH', body: JSON.stringify({ name }) }),
    replaceImage: (campId: number, mapId: number, fd: FormData) =>
      requestFormData<AtlasMap>(`/campaigns/${campId}/atlas/maps/${mapId}/image`, fd, 'PUT'),
    revealMap: (campId: number, mapId: number) =>
      request<AtlasMap>(`/campaigns/${campId}/atlas/maps/${mapId}/reveal`, { method: 'POST' }),
    hideMap: (campId: number, mapId: number) =>
      request<AtlasMap>(`/campaigns/${campId}/atlas/maps/${mapId}/hide`, { method: 'POST' }),
    deleteMap: (campId: number, mapId: number) =>
      request<{ deleted_markers: number }>(`/campaigns/${campId}/atlas/maps/${mapId}`, { method: 'DELETE' }),
    // v = updated_at: a replaced image gets a new URL, so the browser cache never shows the old one.
    mapImageUrl: (campId: number, mapId: number, v: string) =>
      `${BASE_URL}/campaigns/${campId}/atlas/maps/${mapId}/image?init_data=${encodeURIComponent(getInitData())}&v=${encodeURIComponent(v)}`,
    markers: (campId: number, mapId: number) =>
      request<AtlasMarker[]>(`/campaigns/${campId}/atlas/maps/${mapId}/markers`),
    createMarker: (campId: number, mapId: number, body: AtlasMarkerCreate) =>
      request<AtlasMarker>(`/campaigns/${campId}/atlas/maps/${mapId}/markers`, { method: 'POST', body: JSON.stringify(body) }),
    updateMarker: (campId: number, markerId: number, body: AtlasMarkerUpdate) =>
      request<AtlasMarker>(`/campaigns/${campId}/atlas/markers/${markerId}`, { method: 'PATCH', body: JSON.stringify(body) }),
    setVisibility: (campId: number, markerId: number, visibility: MarkerVisibility) =>
      request<AtlasMarker>(`/campaigns/${campId}/atlas/markers/${markerId}/visibility`, {
        method: 'POST',
        body: JSON.stringify({ visibility }),
      }),
    deleteMarker: (campId: number, markerId: number) =>
      request<void>(`/campaigns/${campId}/atlas/markers/${markerId}`, { method: 'DELETE' }),
    types: (campId: number) => request<MarkerType[]>(`/campaigns/${campId}/atlas/marker-types`),
    createType: (campId: number, body: { name: string; icon: string; color: string }) =>
      request<MarkerType>(`/campaigns/${campId}/atlas/marker-types`, { method: 'POST', body: JSON.stringify(body) }),
    deleteType: (campId: number, typeId: number) =>
      request<void>(`/campaigns/${campId}/atlas/marker-types/${typeId}`, { method: 'DELETE' }),
  },

  campaigns: {
    list: () => request<CampaignSummary[]>('/campaigns'),
    create: (name: string) =>
      request<CampaignRead>('/campaigns', { method: 'POST', body: JSON.stringify({ name }) }),
    get: (id: number) => request<CampaignDetail>(`/campaigns/${id}`),
    rename: (id: number, name: string) =>
      request<CampaignRead>(`/campaigns/${id}`, { method: 'PATCH', body: JSON.stringify({ name }) }),
    remove: (id: number) => request<void>(`/campaigns/${id}`, { method: 'DELETE' }),
    regenerateCode: (id: number) =>
      request<{ invite_code: string }>(`/campaigns/${id}/invite-code`, { method: 'POST' }),
    enroll: (code: string, characterId: number) =>
      request<CampaignDetail>('/campaigns/enroll', {
        method: 'POST',
        body: JSON.stringify({ code, character_id: characterId }),
      }),
    activeForMe: () => request<ActiveCampaignSession[]>('/campaigns/active-for-me'),
    setMemberStatus: (id: number, characterId: number, status: CampaignMemberStatus) =>
      request<CampaignDetail>(`/campaigns/${id}/members/${characterId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      }),
    removeMember: (id: number, characterId: number) =>
      request<void>(`/campaigns/${id}/members/${characterId}`, { method: 'DELETE' }),
    schedule: {
      list: (id: number) => request<ScheduleRead[]>(`/campaigns/${id}/schedule`),
      create: (id: number, body: { starts_at: string; note?: string | null }) =>
        request<ScheduleRead>(`/campaigns/${id}/schedule`, { method: 'POST', body: JSON.stringify(body) }),
      update: (id: number, sid: number, body: { starts_at?: string; note?: string | null }) =>
        request<ScheduleRead>(`/campaigns/${id}/schedule/${sid}`, { method: 'PATCH', body: JSON.stringify(body) }),
      remove: (id: number, sid: number) => request<void>(`/campaigns/${id}/schedule/${sid}`, { method: 'DELETE' }),
    },
    joinSession: (id: number, characterId: number) =>
      request<GameSession>(`/campaigns/${id}/session/join`, {
        method: 'POST',
        body: JSON.stringify({ character_id: characterId }),
      }),
  },

  // ---------------------------------------------------------------------------
  // Sessions (invite-code live game sessions)
  // ---------------------------------------------------------------------------
  sessions: {
    me: () => request<GameSession | null>('/sessions/me'),
    create: (title?: string, campaignId?: number) =>
      request<GameSession>('/sessions', {
        method: 'POST',
        body: JSON.stringify(
          campaignId === undefined
            ? { title: title ?? null }
            : { title: title ?? null, campaign_id: campaignId },
        ),
      }),
    stash: (id: number) => request<CampaignStash>(`/sessions/${id}/stash`),
    join: (code: string, characterId: number) =>
      request<GameSession>('/sessions/join', {
        method: 'POST',
        body: JSON.stringify({ code, character_id: characterId }),
      }),
    get: (id: number) => request<GameSession>(`/sessions/${id}`),
    live: (id: number) => request<GameSessionLive>(`/sessions/${id}/live`),
    recap: (id: number) => request<SessionRecap>(`/sessions/${id}/recap`),
    leave: (id: number) =>
      request<void>(`/sessions/${id}/leave`, { method: 'POST' }),
    close: (id: number) =>
      request<void>(`/sessions/${id}/close`, { method: 'POST' }),
    messages: (id: number, afterId = 0) =>
      request<SessionMessage[]>(
        `/sessions/${id}/messages${afterId > 0 ? `?after_id=${afterId}` : ''}`,
      ),
    sendMessage: (id: number, body: string, recipientUserId?: number | null) =>
      request<SessionMessage>(`/sessions/${id}/messages`, {
        method: 'POST',
        body: JSON.stringify({
          body,
          recipient_user_id: recipientUserId ?? null,
        }),
      }),
    getParticipantIdentity: (code: string, userId: number) =>
      request<ParticipantIdentity>(
        `/sessions/${encodeURIComponent(code)}/participants/${userId}/identity`
      ),
    getFeed: (
      code: string,
      opts?: { since?: string; before?: string; limit?: number }
    ) => {
      const params = new URLSearchParams()
      if (opts?.since) params.set('since', opts.since)
      if (opts?.before) params.set('before', opts.before)
      if (opts?.limit) params.set('limit', String(opts.limit))
      const q = params.toString()
      return request<SessionFeedResponse>(
        `/sessions/${encodeURIComponent(code)}/feed${q ? `?${q}` : ''}`
      )
    },
    trade: (sessionId: number, body: TradeRequest) =>
      request<CharacterFull>(`/sessions/${sessionId}/trade`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    stashPut: (sessionId: number, body: StashMoveRequest & { from_character_id: number }) =>
      request<CharacterFull>(`/sessions/${sessionId}/stash/put`, { method: 'POST', body: JSON.stringify(body) }),
    stashTake: (sessionId: number, body: StashMoveRequest & { to_character_id: number }) =>
      request<CharacterFull>(`/sessions/${sessionId}/stash/take`, { method: 'POST', body: JSON.stringify(body) }),
    stashGmAdd: (sessionId: number, body: { item?: GrantItemPayload; coins?: StashMoveRequest['coins'] }) =>
      request<CampaignStash>(`/sessions/${sessionId}/stash/gm-add`, { method: 'POST', body: JSON.stringify(body) }),
    stashGmRemove: (sessionId: number, body: StashMoveRequest) =>
      request<CampaignStash>(`/sessions/${sessionId}/stash/gm-remove`, { method: 'POST', body: JSON.stringify(body) }),
    grantItem: (
      sessionId: number,
      payload: { recipient_user_ids: number[]; item: GrantItemPayload },
    ) =>
      request<GMGrantItemResponse>(`/sessions/${sessionId}/gm/grant_item`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    encounter: {
      create: (sessionId: number, mode: EncounterMode) =>
        request<EncounterLive>(`/sessions/${sessionId}/encounter`, {
          method: 'POST',
          body: JSON.stringify({ mode }),
        }),
      addCombatants: (
        sessionId: number,
        payload: {
          name: string
          count?: number
          initiative_mod?: number
          max_hp?: number
          ac?: number
        },
      ) =>
        request<EncounterLive>(`/sessions/${sessionId}/encounter/combatants`, {
          method: 'POST',
          body: JSON.stringify(payload),
        }),
      rollInitiative: (sessionId: number, combatantId: number, die?: D20Roll) =>
        request<EncounterLive>(
          `/sessions/${sessionId}/encounter/combatants/${combatantId}/initiative`,
          { method: 'POST', body: JSON.stringify(typeof die === 'object' ? d20Fields(die) : { die: die ?? null }) },
        ),
      patchCombatant: (sessionId: number, combatantId: number, patch: CombatantPatch) =>
        request<EncounterLive>(
          `/sessions/${sessionId}/encounter/combatants/${combatantId}`,
          { method: 'PATCH', body: JSON.stringify(patch) },
        ),
      applyCondition: (sessionId: number, combatantId: number, body: GmConditionApply) =>
        request<EncounterLive>(
          `/sessions/${sessionId}/encounter/combatants/${combatantId}/conditions`,
          { method: 'POST', body: JSON.stringify(body) },
        ),
      removeCondition: (sessionId: number, combatantId: number, slug: string) =>
        request<EncounterLive>(
          `/sessions/${sessionId}/encounter/combatants/${combatantId}/conditions/${encodeURIComponent(slug)}`,
          { method: 'DELETE' },
        ),
      resolveSave: (sessionId: number, saveId: number, passed: boolean) =>
        request<EncounterLive>(
          `/sessions/${sessionId}/encounter/pending-saves/${saveId}/resolve`,
          { method: 'POST', body: JSON.stringify({ passed }) },
        ),
      removeCombatant: (sessionId: number, combatantId: number) =>
        request<EncounterLive>(
          `/sessions/${sessionId}/encounter/combatants/${combatantId}`,
          { method: 'DELETE' },
        ),
      syncPcs: (sessionId: number) =>
        request<EncounterLive>(`/sessions/${sessionId}/encounter/sync-pcs`, {
          method: 'POST',
        }),
      start: (sessionId: number, autoRollMissing = false) =>
        request<EncounterLive>(`/sessions/${sessionId}/encounter/start`, {
          method: 'POST',
          body: JSON.stringify({ auto_roll_missing: autoRollMissing }),
        }),
      nextTurn: (sessionId: number) =>
        request<EncounterLive>(`/sessions/${sessionId}/encounter/next-turn`, {
          method: 'POST',
        }),
      prevTurn: (sessionId: number) =>
        request<EncounterLive>(`/sessions/${sessionId}/encounter/prev-turn`, {
          method: 'POST',
        }),
      reorder: (sessionId: number, combatantIds: number[]) =>
        request<EncounterLive>(`/sessions/${sessionId}/encounter/reorder`, {
          method: 'POST',
          body: JSON.stringify({ combatant_ids: combatantIds }),
        }),
      end: (sessionId: number) =>
        request<EncounterLive>(`/sessions/${sessionId}/encounter/end`, {
          method: 'POST',
        }),
    },
  },
}

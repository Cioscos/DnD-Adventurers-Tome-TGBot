/**
 * Typed API client for the FastAPI backend.
 *
 * Every request includes X-Telegram-Init-Data for server-side HMAC verification.
 * The base URL is read from VITE_API_BASE_URL (set in .env.local for dev).
 */

import { getInitData } from '@/auth/telegram'
import type {
  Ability,
  CharacterFull,
  CharacterSummary,
  Currency,
  DiceRollResult,
  HistoryEntry,
  Item,
  MapEntry,
  Note,
  Spell,
  SpellSlot,
} from '@/types'

export type RollResult = {
  die: number
  bonus: number
  total: number
  is_critical: boolean
  is_fumble: boolean
  description?: string
}

export type WeaponAttackResult = {
  weapon_name: string
  to_hit_die: number
  to_hit_bonus: number
  to_hit_total: number
  is_critical: boolean
  is_fumble: boolean
  damage_dice: string
  damage_rolls: number[]
  damage_bonus: number
  damage_total: number
}

export type HitDiceSpendResult = {
  rolls: number[]
  con_bonus: number
  healed: number
  new_current_hp: number
}

export type DeathSaveRollResult = {
  die: number
  outcome: 'nat20' | 'nat1' | 'success' | 'failure'
  successes: number
  failures: number
  stable: boolean
  revived: boolean
  current_hp: number
}

export type ConcentrationSaveResult = {
  die: number
  bonus: number
  total: number
  dc: number
  success: boolean
  lost_concentration: boolean
  is_critical: boolean
  is_fumble: boolean
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string
  ) {
    super(`API ${status}: ${detail}`)
    this.name = 'ApiError'
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const initData = getInitData()
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Telegram-Init-Data': initData,
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
): Promise<T> {
  const initData = getInitData()
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'X-Telegram-Init-Data': initData,
    },
    body: formData,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, body.detail ?? res.statusText)
  }
  return res.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Characters
// ---------------------------------------------------------------------------

export const api = {
  characters: {
    list: () => request<CharacterSummary[]>('/characters'),
    get: (id: number) => request<CharacterFull>(`/characters/${id}`),
    create: (name: string) =>
      request<CharacterFull>('/characters', {
        method: 'POST',
        body: JSON.stringify({ name }),
      }),
    update: (id: number, data: Record<string, unknown>) =>
      request<CharacterFull>(`/characters/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      request<void>(`/characters/${id}`, { method: 'DELETE' }),

    // HP
    updateHp: (id: number, op: string, value: number) =>
      request<CharacterFull>(`/characters/${id}/hp`, {
        method: 'PATCH',
        body: JSON.stringify({ op, value }),
      }),
    rest: (id: number, restType: 'long' | 'short', hitDiceUsed?: number) =>
      request<CharacterFull>(`/characters/${id}/rest`, {
        method: 'POST',
        body: JSON.stringify({ rest_type: restType, hit_dice_used: hitDiceUsed }),
      }),
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
    updateConditions: (id: number, conditions: Record<string, unknown>) =>
      request<CharacterFull>(`/characters/${id}/conditions`, {
        method: 'PATCH',
        body: JSON.stringify({ conditions }),
      }),
    updateInspiration: (id: number, heroic_inspiration: boolean) =>
      request<CharacterFull>(`/characters/${id}/inspiration`, {
        method: 'PATCH',
        body: JSON.stringify({ heroic_inspiration }),
      }),
    updateXP: (id: number, data: { add?: number; set?: number }) =>
      request<CharacterFull>(`/characters/${id}/xp`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),

    // Roll endpoints
    rollSkill: (id: number, skillName: string) =>
      request<RollResult>(`/characters/${id}/skills/${encodeURIComponent(skillName)}/roll`, {
        method: 'POST',
      }),
    rollSavingThrow: (id: number, ability: string) =>
      request<RollResult>(`/characters/${id}/saving_throws/${encodeURIComponent(ability)}/roll`, {
        method: 'POST',
      }),

    // Hit dice spending
    spendHitDice: (id: number, classId: number, count: number) =>
      request<HitDiceSpendResult>(`/characters/${id}/hit_dice/spend`, {
        method: 'POST',
        body: JSON.stringify({ class_id: classId, count }),
      }),

    // Death save roll
    rollDeathSave: (id: number) =>
      request<DeathSaveRollResult>(`/characters/${id}/death_saves/roll`, {
        method: 'POST',
      }),
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
    addResource: (charId: number, classId: number, data: Record<string, unknown>) =>
      request<unknown>(`/characters/${charId}/classes/${classId}/resources`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    updateResource: (charId: number, classId: number, resId: number, data: Record<string, unknown>) =>
      request<unknown>(`/characters/${charId}/classes/${classId}/resources/${resId}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    deleteResource: (charId: number, classId: number, resId: number) =>
      request<void>(`/characters/${charId}/classes/${classId}/resources/${resId}`, {
        method: 'DELETE',
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
    use: (charId: number, spellId: number, slotLevel: number) =>
      request<CharacterFull>(`/characters/${charId}/spells/${spellId}/use`, {
        method: 'POST',
        body: JSON.stringify({ slot_level: slotLevel }),
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
    attack: (charId: number, itemId: number) =>
      request<WeaponAttackResult>(`/characters/${charId}/items/${itemId}/attack`, {
        method: 'POST',
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
  },

  // ---------------------------------------------------------------------------
  // Abilities (features)
  // ---------------------------------------------------------------------------
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

  // ---------------------------------------------------------------------------
  // Notes
  // ---------------------------------------------------------------------------
  notes: {
    list: (charId: number) => request<Note[]>(`/characters/${charId}/notes`),
    add: (charId: number, title: string, body: string) =>
      request<Note[]>(`/characters/${charId}/notes`, {
        method: 'POST',
        body: JSON.stringify({ title, body }),
      }),
    update: (charId: number, title: string, body: string) =>
      request<Note[]>(`/characters/${charId}/notes/${encodeURIComponent(title)}`, {
        method: 'PATCH',
        body: JSON.stringify({ body }),
      }),
    remove: (charId: number, title: string) =>
      request<Note[]>(`/characters/${charId}/notes/${encodeURIComponent(title)}`, {
        method: 'DELETE',
      }),
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
  },

  // ---------------------------------------------------------------------------
  // Dice
  // ---------------------------------------------------------------------------
  dice: {
    roll: (charId: number, count: number, die: string) =>
      request<DiceRollResult>(`/characters/${charId}/dice/roll`, {
        method: 'POST',
        body: JSON.stringify({ count, die }),
      }),
    history: (charId: number) => request<DiceRollResult[]>(`/characters/${charId}/dice/history`),
    clearHistory: (charId: number) =>
      request<void>(`/characters/${charId}/dice/history`, { method: 'DELETE' }),
  },

  // ---------------------------------------------------------------------------
  // History
  // ---------------------------------------------------------------------------
  history: {
    get: (charId: number) => request<HistoryEntry[]>(`/characters/${charId}/history`),
    clear: (charId: number) =>
      request<void>(`/characters/${charId}/history`, { method: 'DELETE' }),
  },
}

export { ApiError }

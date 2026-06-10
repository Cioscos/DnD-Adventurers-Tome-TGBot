import { describe, it, expect } from 'vitest'
import {
  readQuickActions,
  resolveQuickActions,
  quickActionKey,
  QUICK_ACTIONS_MAX,
  type QuickActionEntry,
} from '@/lib/quickActions'
import type { CharacterFull } from '@/types'

function makeChar(partial: Partial<CharacterFull>): CharacterFull {
  return {
    id: 7,
    name: 'Eroe',
    hit_points: 10,
    spells: [],
    items: [],
    abilities: [],
    ...partial,
  } as CharacterFull
}

const weapon = (id: number, name: string) =>
  ({ id, name, weight: 1, quantity: 1, item_type: 'weapon', is_equipped: false })

const generic = (id: number, name: string) =>
  ({ id, name, weight: 1, quantity: 1, item_type: 'generic', is_equipped: false })

const spell = (id: number, name: string) =>
  ({ id, name, level: 1, is_concentration: false, is_ritual: false, is_pinned: false, is_prepared: true })

describe('readQuickActions', () => {
  it('returns [] for missing or malformed settings', () => {
    expect(readQuickActions(undefined)).toEqual([])
    expect(readQuickActions({})).toEqual([])
    expect(readQuickActions({ quick_actions: 'nope' })).toEqual([])
  })
})

describe('resolveQuickActions', () => {
  it('keeps saved order and resolves against current data', () => {
    const char = makeChar({
      items: [weapon(1, 'Spada')],
      spells: [spell(9, 'Dardo Incantato')],
    })
    const entries: QuickActionEntry[] = [
      { type: 'save', ability: 'dexterity' },
      { type: 'weapon', id: 1 },
      { type: 'spell', id: 9 },
    ]
    const resolved = resolveQuickActions(char, entries)
    expect(resolved.map((r) => r.type)).toEqual(['save', 'weapon', 'spell'])
    expect(resolved.map((r) => r.key)).toEqual(['save-dexterity', 'weapon-1', 'spell-9'])
  })

  it('drops stale entries: deleted items/spells, non-weapons, unknown abilities', () => {
    const char = makeChar({ items: [generic(2, 'Corda')] })
    const entries: QuickActionEntry[] = [
      { type: 'weapon', id: 99 },          // arma eliminata
      { type: 'weapon', id: 2 },           // non è un'arma
      { type: 'spell', id: 5 },            // incantesimo eliminato
      { type: 'save', ability: 'luck' },   // ability inesistente
      { type: 'save', ability: 'wisdom' },
    ]
    const resolved = resolveQuickActions(char, entries)
    expect(resolved).toHaveLength(1)
    expect(resolved[0]).toMatchObject({ type: 'save', ability: 'wisdom' })
  })

  it('caps at QUICK_ACTIONS_MAX', () => {
    const entries: QuickActionEntry[] = Array.from({ length: 10 }, () => ({
      type: 'save' as const,
      ability: 'strength',
    }))
    const char = makeChar({})
    expect(resolveQuickActions(char, entries)).toHaveLength(QUICK_ACTIONS_MAX)
    expect(QUICK_ACTIONS_MAX).toBe(8)
  })
})

describe('quickActionKey', () => {
  it('builds stable keys per entry type', () => {
    expect(quickActionKey({ type: 'weapon', id: 3 })).toBe('weapon-3')
    expect(quickActionKey({ type: 'save', ability: 'charisma' })).toBe('save-charisma')
    expect(quickActionKey({ type: 'spell', id: 4 })).toBe('spell-4')
  })
})

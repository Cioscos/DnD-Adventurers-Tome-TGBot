import { describe, it, expect } from 'vitest'
import {
  quickActionKey,
  resolveQuickActions,
  hitDiceRemaining,
  QUICK_ACTIONS_MAX,
  type QuickActionEntry,
} from '@/lib/quickActions'
import type { CharacterFull, CharacterClass } from '@/types'

const char = {
  id: 1,
  heroic_inspiration: true,
  items: [
    { id: 10, name: 'Spada', item_type: 'weapon' },
    { id: 11, name: 'Frecce', item_type: 'ammunition', quantity: 20 },
  ],
  spells: [{ id: 20, name: 'Dardo Incantato', level: 1 }],
  abilities: [
    { id: 30, name: 'Sanità', is_passive: false, is_active: true, max_uses: 200, uses: 150, restoration_type: 'manual', is_class_feature: false },
    { id: 31, name: 'Passiva', is_passive: true, is_active: false, restoration_type: 'none', is_class_feature: false },
    { id: 32, name: 'Senza usi', is_passive: false, is_active: true, restoration_type: 'none', is_class_feature: false },
  ],
  classes: [
    { id: 40, class_name: 'fighter', level: 5, hit_die: 10, hit_dice_used: 2 },
  ],
} as unknown as CharacterFull

describe('quickActionKey', () => {
  it('genera chiavi univoche per ogni tipo', () => {
    expect(quickActionKey({ type: 'weapon', id: 10 })).toBe('weapon-10')
    expect(quickActionKey({ type: 'save', ability: 'dexterity' })).toBe('save-dexterity')
    expect(quickActionKey({ type: 'ability', id: 30 })).toBe('ability-30')
    expect(quickActionKey({ type: 'counter_ability', id: 30 })).toBe('counter_ability-30')
    expect(quickActionKey({ type: 'counter_inspiration' })).toBe('counter_inspiration')
    expect(quickActionKey({ type: 'counter_ammo', id: 11 })).toBe('counter_ammo-11')
    expect(quickActionKey({ type: 'hit_die', classId: 40 })).toBe('hit_die-40')
    expect(quickActionKey({ type: 'rest', rest: 'long' })).toBe('rest-long')
  })
})

describe('hitDiceRemaining', () => {
  it('calcola level - used, mai negativo', () => {
    expect(hitDiceRemaining({ level: 5, hit_dice_used: 2 } as CharacterClass)).toBe(3)
    expect(hitDiceRemaining({ level: 2, hit_dice_used: 9 } as CharacterClass)).toBe(0)
    expect(hitDiceRemaining({ level: 3 } as CharacterClass)).toBe(3)
  })
})

describe('resolveQuickActions', () => {
  it('risolve tutti i nuovi tipi validi', () => {
    const entries: QuickActionEntry[] = [
      { type: 'ability', id: 30 },
      { type: 'counter_ability', id: 30 },
      { type: 'counter_inspiration' },
      { type: 'counter_ammo', id: 11 },
      { type: 'hit_die', classId: 40 },
      { type: 'rest', rest: 'short' },
    ]
    const resolved = resolveQuickActions(char, entries)
    expect(resolved.map((r) => r.type)).toEqual([
      'ability', 'counter_ability', 'counter_inspiration', 'counter_ammo', 'hit_die', 'rest',
    ])
    const hd = resolved.find((r) => r.type === 'hit_die')
    expect(hd && 'remaining' in hd && hd.remaining).toBe(3)
  })

  it('scarta voci stale e tipi sconosciuti', () => {
    const entries = [
      { type: 'ability', id: 31 },          // passiva → out
      { type: 'ability', id: 32 },          // senza max_uses → out
      { type: 'ability', id: 999 },         // eliminata → out
      { type: 'counter_ammo', id: 10 },     // non è ammunition → out
      { type: 'hit_die', classId: 999 },    // classe rimossa → out
      { type: 'gadget', id: 1 },            // tipo ignoto → out, senza throw
    ] as unknown as QuickActionEntry[]
    expect(resolveQuickActions(char, entries)).toEqual([])
  })

  it('tronca a QUICK_ACTIONS_MAX (12)', () => {
    const entries: QuickActionEntry[] = Array.from({ length: 15 }, () => ({ type: 'rest', rest: 'long' as const }))
    expect(QUICK_ACTIONS_MAX).toBe(12)
    expect(resolveQuickActions(char, entries)).toHaveLength(12)
  })
})

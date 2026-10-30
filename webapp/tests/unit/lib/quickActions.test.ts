import { describe, it, expect } from 'vitest'
import {
  quickActionKey,
  resolveQuickActions,
  readQuickActions,
  defaultQuickActions,
  effectiveQuickActions,
  hasCustomQuickActions,
  hitDiceRemaining,
  isAmmunitionItem,
  QUICK_ACTIONS_MAX,
  type QuickActionEntry,
} from '@/lib/quickActions'
import type { CharacterFull, CharacterClass, Item } from '@/types'

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

  it('scarta elementi malformati (null, numeri, stringhe) senza throw', () => {
    const entries = [null, 42, 'x'] as unknown as QuickActionEntry[]
    expect(resolveQuickActions(char, entries)).toEqual([])
  })

  it('tronca a QUICK_ACTIONS_MAX (12)', () => {
    const entries: QuickActionEntry[] = Array.from({ length: 15 }, () => ({ type: 'rest', rest: 'long' as const }))
    expect(QUICK_ACTIONS_MAX).toBe(12)
    expect(resolveQuickActions(char, entries)).toHaveLength(12)
  })
})

describe('readQuickActions', () => {
  it('array valido → passthrough, altrimenti []', () => {
    const entries = [{ type: 'weapon', id: 10 }]
    expect(readQuickActions({ quick_actions: entries })).toEqual(entries)
    expect(readQuickActions(undefined)).toEqual([])
    expect(readQuickActions({})).toEqual([])
    expect(readQuickActions({ quick_actions: 'x' })).toEqual([])
    expect(readQuickActions({ quick_actions: 42 })).toEqual([])
  })
})

describe('resolveQuickActions — tipi legacy (weapon/save/spell)', () => {
  it('risolve le voci valide preservando l\'ordine misto', () => {
    const entries: QuickActionEntry[] = [
      { type: 'spell', id: 20 },
      { type: 'save', ability: 'dexterity' },
      { type: 'weapon', id: 10 },
    ]
    const resolved = resolveQuickActions(char, entries)
    expect(resolved.map((r) => r.key)).toEqual(['spell-20', 'save-dexterity', 'weapon-10'])
  })

  it('scarta arma non-weapon, save sconosciuto, incantesimo eliminato', () => {
    const entries: QuickActionEntry[] = [
      { type: 'weapon', id: 11 },          // è ammunition, non weapon
      { type: 'save', ability: 'luck' },   // ability inesistente
      { type: 'spell', id: 999 },          // eliminato
    ]
    expect(resolveQuickActions(char, entries)).toEqual([])
  })
})

describe('quickActionKey — variante spell', () => {
  it('genera spell-<id>', () => {
    expect(quickActionKey({ type: 'spell', id: 20 })).toBe('spell-20')
  })
})

describe('isAmmunitionItem', () => {
  it('riconosce tipo munizione e gear nello slot munizioni, non il gear semplice', () => {
    expect(isAmmunitionItem({ item_type: 'ammunition', equipment_slot: null } as unknown as Item)).toBe(true)
    expect(isAmmunitionItem({ item_type: 'gear', equipment_slot: 'ammunition' } as unknown as Item)).toBe(true)
    expect(isAmmunitionItem({ item_type: 'gear', equipment_slot: null } as unknown as Item)).toBe(false)
  })

  it('resolveQuickActions mantiene un gear nello slot munizioni come counter_ammo', () => {
    const c = { ...char, items: [{ id: 50, name: 'Quadrelli', item_type: 'gear', equipment_slot: 'ammunition', quantity: 5 }] } as unknown as CharacterFull
    const r = resolveQuickActions(c, [{ type: 'counter_ammo', id: 50 }])
    expect(r.map((x) => x.type)).toEqual(['counter_ammo'])
  })
})

describe('defaultQuickActions', () => {
  const base = (over: Record<string, unknown>) => ({ ...char, ...over }) as unknown as CharacterFull

  it('builds defaults from equipped weapons, damaging spells, abilities, hit dice, short rest and inspiration', () => {
    const c = base({
      items: [
        { id: 10, item_type: 'weapon', is_equipped: true },
        { id: 12, item_type: 'weapon', is_equipped: false },
      ],
      spells: [
        { id: 20, level: 0, damage_dice: '1d10' },
        { id: 21, level: 1, damage_dice: null },
      ],
    })
    expect(defaultQuickActions(c)).toEqual([
      { type: 'weapon', id: 10 },
      { type: 'spell', id: 20 },
      { type: 'ability', id: 30 },
      { type: 'hit_die', classId: 40 },
      { type: 'rest', rest: 'short' },
      { type: 'counter_inspiration' },
    ])
  })

  it('skips unprepared levelled spells for preparing casters', () => {
    const spells = [
      { id: 20, level: 0, damage_dice: '1d10', is_prepared: false },
      { id: 21, level: 1, damage_dice: '3d4', is_prepared: false },
      { id: 22, level: 1, damage_dice: '2d6', is_prepared: true },
    ]
    const prep = defaultQuickActions(base({ items: [], spells, spellcasting: { has_preparing_class: true } }))
    expect(prep.filter((e) => e.type === 'spell')).toEqual([
      { type: 'spell', id: 20 }, { type: 'spell', id: 22 },
    ])
    const known = defaultQuickActions(base({ items: [], spells, spellcasting: { has_preparing_class: false } }))
    expect(known.filter((e) => e.type === 'spell')).toHaveLength(3)
  })

  it('caps defaults at 12', () => {
    const items = Array.from({ length: 20 }, (_, i) => ({ id: 100 + i, item_type: 'weapon', is_equipped: true }))
    expect(defaultQuickActions(base({ items }))).toHaveLength(QUICK_ACTIONS_MAX)
  })
})

describe('effectiveQuickActions', () => {
  it('follows the character while the list is not customized', () => {
    const c = { ...char, settings: {}, items: [] } as unknown as CharacterFull
    expect(effectiveQuickActions(c)).not.toContainEqual({ type: 'weapon', id: 50 })
    const c2 = { ...c, items: [{ id: 50, item_type: 'weapon', is_equipped: true }] } as unknown as CharacterFull
    expect(effectiveQuickActions(c2)).toContainEqual({ type: 'weapon', id: 50 })
    expect(hasCustomQuickActions(c.settings)).toBe(false)
  })

  it('keeps an emptied list empty', () => {
    const c = { ...char, settings: { quick_actions: [] } } as unknown as CharacterFull
    expect(effectiveQuickActions(c)).toEqual([])
    expect(hasCustomQuickActions(c.settings)).toBe(true)
  })
})

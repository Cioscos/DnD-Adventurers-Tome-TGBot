import { describe, it, expect } from 'vitest'
import { groupForTurn, parseCastingTime } from '@/lib/turnGrouping'
import type { CharacterFull } from '@/types'

// Stessa tabella di tests/services/test_actions_parser.py::CASTING_TIME_CASES.
const CASTING_TIME_CASES: [string | null, string | null][] = [
  ['1 azione', 'action'],
  ['1 action', 'action'],
  ['1 Action', 'action'],
  ['1 azione bonus', 'bonus_action'],
  ['1 bonus action', 'bonus_action'],
  ['1 Bonus Action', 'bonus_action'],
  ['1 reazione', 'reaction'],
  ['1 reaction', 'reaction'],
  ['1 reazione, che effettui quando vieni colpito', 'reaction'],
  ['1 reaction, which you take when you are hit', 'reaction'],
  ['1 azione, o 8 ore', 'action'],
  ['  1 azione bonus  ', 'bonus_action'],
  ['1 minuto', null],
  ['10 minutes', null],
  ['1 ora', null],
  ['8 hours', null],
  ['', null],
  [null, null],
]

describe('parseCastingTime', () => {
  it.each(CASTING_TIME_CASES)('%j -> %s', (text, expected) => {
    expect(parseCastingTime(text)).toBe(expected)
  })
})

const spell = (id: number, o: Record<string, unknown>) =>
  ({ id, name: `S${id}`, level: 1, is_prepared: true, is_concentration: false, is_ritual: false, is_pinned: false, ...o })

const char = {
  items: [
    { id: 1, name: 'Spada', item_type: 'weapon', is_equipped: true },
    { id: 2, name: 'Arco', item_type: 'weapon', is_equipped: false },
  ],
  spells: [
    spell(10, { casting_time: '1 azione' }),
    spell(11, { casting_time: '1 azione bonus' }),
    spell(12, { casting_time: '1 minuto' }),
    spell(13, { casting_time: '1 azione', is_prepared: false }),
    spell(14, { casting_time: '1 azione', level: 0, is_prepared: false }),
  ],
  abilities: [
    { id: 20, name: 'Scudo', is_passive: false, action_type: 'reaction' },
    { id: 21, name: 'Passiva', is_passive: true, action_type: 'action' },
    { id: 22, name: 'Libera', is_passive: false, action_type: null },
  ],
  spellcasting: { has_preparing_class: true },
} as unknown as CharacterFull

describe('groupForTurn', () => {
  const g = groupForTurn(char)
  const ids = (list: { kind: string; id: string }[]) => list.map((e) => `${e.kind}:${e.id}`)

  it('equipped weapons then unarmed go to attacks, not to action', () => {
    expect(ids(g.attacks)).toEqual(['weapon:1', 'weapon:unarmed'])
    expect(ids(g.action).filter((x) => x.startsWith('weapon:'))).toEqual([])
  })
  it('bonus action spell lands in bonus', () => {
    expect(ids(g.bonus_action)).toEqual(['spell:11'])
  })
  it('reaction ability lands in reaction, with the standard opportunity attack', () => {
    expect(ids(g.reaction)).toEqual(expect.arrayContaining(['ability:20', 'standard:opportunity']))
  })
  it('unprepared spell is excluded, cantrip kept, long casting time goes to other', () => {
    const all = Object.values(g).flat().map((e) => `${e.kind}:${e.id}`)
    expect(all).not.toContain('spell:13')
    expect(ids(g.action)).toContain('spell:14')
    expect(ids(g.other)).toEqual(expect.arrayContaining(['spell:12', 'ability:22']))
    expect(all).not.toContain('ability:21')
  })
})

describe('azioni standard per edizione', () => {
  const std = (c: CharacterFull) => groupForTurn(c).action.filter((e) => e.kind === 'standard').map((e) => e.id)
  it('2014 non ha Influenzare e Studiare', () => {
    expect(std({ ...char, rules_edition: '2014' } as CharacterFull)).not.toEqual(expect.arrayContaining(['influence']))
    expect(std({ ...char, rules_edition: '2014' } as CharacterFull)).not.toContain('study')
  })
  it('2024 aggiunge Influenzare e Studiare', () => {
    expect(std({ ...char, rules_edition: '2024' } as CharacterFull)).toEqual(expect.arrayContaining(['influence', 'study']))
  })
})

describe('Campione degli Antichi (punto 42)', () => {
  const ids = (list: { kind: string; id: string }[]) => list.map((e) => `${e.kind}:${e.id}`)

  it('groups by the casting time the server sends: the server already rewrites it to a bonus action while the state is on', () => {
    const c = {
      ...char,
      active_states: [{ key: 'elder_champion' }],
      spells: [
        spell(30, { casting_time: '1 azione bonus', class_id: 1 }),
        spell(31, { casting_time: '1 azione', class_id: 2 }),
        spell(32, { casting_time: '1 reazione', class_id: 1 }),
        spell(33, { casting_time: '1 minuto', class_id: 1 }),
      ],
    }
    const g = groupForTurn(c as unknown as CharacterFull)
    expect(ids(g.bonus_action)).toContain('spell:30')
    expect(ids(g.action)).toContain('spell:31')
    expect(ids(g.reaction)).toContain('spell:32')
    expect(ids(g.other)).toContain('spell:33')
  })

  it('does not move anything by itself: with the state on but the server time unchanged, the spell stays on the action', () => {
    const c = { ...char, classes: [{ id: 1, class_name: 'paladin' }], active_states: [{ key: 'elder_champion' }],
      spells: [spell(40, { casting_time: '1 azione', class_id: 1 })] }
    expect(ids(groupForTurn(c as unknown as CharacterFull).action)).toContain('spell:40')
  })
})

describe('Punizione Divina 2024', () => {
  const ids = (list: { kind: string; id: string }[]) => list.map((e) => `${e.kind}:${e.id}`)
  it('has no row in the turn: it is chosen after a hit, never cast from the list', () => {
    const c = { items: [], abilities: [], rules_edition: '2024', active_states: [], classes: [],
      spells: [spell(7, { casting_time: '1 azione bonus', srd_index: 'divine-smite' }), spell(8, { casting_time: '1 azione bonus' })] }
    expect(ids(groupForTurn(c as unknown as CharacterFull).bonus_action)).toEqual(['spell:8'])
  })
})

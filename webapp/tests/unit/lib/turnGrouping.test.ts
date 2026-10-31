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

  it('equipped weapons and unarmed go to action', () => {
    expect(ids(g.action)).toEqual(expect.arrayContaining(['weapon:1', 'weapon:unarmed']))
    expect(ids(g.action)).not.toContain('weapon:2')
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

import { describe, it, expect } from 'vitest'
import { familiarWarning, wildShapeWarning, wildShapeMaxCr, monsterToStatblock } from '@/lib/companionRules'
import type { MonsterEntry } from '@/lib/srd/catalog'

const beast = (cr: number, speed: Record<string, number> = { walk_ft: 30 }, type = 'beast') =>
  ({ index: 'x', type, challenge_rating: cr, speed })

describe('familiarWarning', () => {
  it('allows SRD familiar forms and warns otherwise', () => {
    expect(familiarWarning({ index: 'owl' })).toBeNull()
    expect(familiarWarning({ index: 'poisonous-snake' })).toBeNull()
    expect(familiarWarning({ index: 'wolf' })).toBe('character.extras.warn.familiar_form')
  })
})

describe('wildShapeWarning', () => {
  it('applies CR limits by druid level', () => {
    expect(wildShapeMaxCr(2, false)).toBe(0.25)
    expect(wildShapeMaxCr(4, false)).toBe(0.5)
    expect(wildShapeMaxCr(8, false)).toBe(1)
    expect(wildShapeMaxCr(2, true)).toBe(1)
    expect(wildShapeMaxCr(6, true)).toBe(2)
    expect(wildShapeMaxCr(18, true)).toBe(6)
    expect(wildShapeWarning(beast(0.5), 2, false)).toBe('character.extras.warn.cr')
    expect(wildShapeWarning(beast(0.5), 4, false)).toBeNull()
    expect(wildShapeWarning(beast(1), 2, true)).toBeNull()
  })
  it('blocks fly before 8 and swim before 4', () => {
    expect(wildShapeWarning(beast(0.25, { walk_ft: 10, fly_ft: 60 }), 6, true)).toBe('character.extras.warn.fly')
    expect(wildShapeWarning(beast(0.25, { walk_ft: 10, fly_ft: 60 }), 8, false)).toBeNull()
    expect(wildShapeWarning(beast(0.25, { walk_ft: 10, swim_ft: 30 }), 2, false)).toBe('character.extras.warn.swim')
    expect(wildShapeWarning(beast(0.25, { walk_ft: 10, swim_ft: 30 }), 4, false)).toBeNull()
  })
  it('2024: swimming is free, Moon CR is level/3 from level 3', () => {
    expect(wildShapeWarning(beast(0.25, { walk_ft: 10, swim_ft: 30 }), 2, false, '2024')).toBeNull()
    expect(wildShapeWarning(beast(0.25, { walk_ft: 10, fly_ft: 60 }), 6, false, '2024')).toBe('character.extras.warn.fly')
    expect(wildShapeMaxCr(3, true, '2024')).toBe(1)
    expect(wildShapeMaxCr(2, true, '2024')).toBe(0.25)
    expect(wildShapeMaxCr(6, true, '2024')).toBe(2)
  })
  it('Elemental Wild Shape: the four elementals pass for the Moon from level 10 (2014), nobody else', () => {
    const elemental = (index: string) => ({ index, type: 'elemental', challenge_rating: 5, speed: { walk_ft: 50 } })
    expect(wildShapeWarning(elemental('fire-elemental'), 10, true)).toBeNull()
    expect(wildShapeWarning(elemental('water-elemental'), 14, true)).toBeNull()
    expect(wildShapeWarning(elemental('fire-elemental'), 9, true)).toBe('character.extras.warn.not_beast')
    expect(wildShapeWarning(elemental('fire-elemental'), 10, false)).toBe('character.extras.warn.not_beast')
    expect(wildShapeWarning(elemental('fire-elemental'), 10, true, '2024')).toBe('character.extras.warn.not_beast')
    expect(wildShapeWarning(elemental('invisible-stalker'), 10, true)).toBe('character.extras.warn.not_beast')
  })
  it('requires a beast', () => {
    expect(wildShapeWarning(beast(0.25, { walk_ft: 30 }, 'monstrosity'), 8, false)).toBe('character.extras.warn.not_beast')
  })
})

describe('monsterToStatblock', () => {
  it('flags English fallbacks and turns flat damage into NdX', () => {
    const e = {
      index: 'bat', size: 'tiny', type: 'beast', speed: {}, abilities: {}, challenge_rating: 0,
      name: { en: 'Bat' }, armor_class: 12, hit_points: 1,
      traits: [{ name: { en: 'Keen', it: 'Acuto' }, desc: { en: 'x' } }],
      actions: [{ name: { en: 'Bite', it: 'Morso' }, desc: { en: 'y', it: 'z' }, attack_bonus: 0, damage_dice: '1', damage_type: 'piercing' }],
    } as unknown as MonsterEntry
    const sb = monsterToStatblock(e, 'it')
    expect(sb.traits?.[0]).toMatchObject({ name: 'Acuto', desc: 'x', en: true })
    expect(sb.actions?.[0]).toMatchObject({ name: 'Morso', damage_dice: '1d1' })
    expect(sb.actions?.[0].en).toBeUndefined()
  })

  it('carries the skill and saving throw bonuses of the creature (the server gives them to a druid in beast form)', () => {
    const wolf = {
      index: 'wolf', size: 'medium', type: 'beast', speed: {}, abilities: { dex: 15 }, challenge_rating: 0.25,
      name: { en: 'Wolf' }, armor_class: 13, hit_points: 11, traits: [], actions: [],
      skills: { perception: 3, stealth: 4 }, saves: { con: 6 },
    } as unknown as MonsterEntry
    expect(monsterToStatblock(wolf, 'it')).toMatchObject({ skills: { perception: 3, stealth: 4 }, saves: { con: 6 } })
  })

  it('leaves them out when the creature has none', () => {
    const bat = { index: 'bat', size: 'tiny', type: 'beast', speed: {}, abilities: {}, challenge_rating: 0, name: { en: 'Bat' },
      armor_class: 12, hit_points: 1, traits: [], actions: [], skills: {}, saves: {} } as unknown as MonsterEntry
    const sb = monsterToStatblock(bat, 'it')
    expect(sb.skills).toBeUndefined()
    expect(sb.saves).toBeUndefined()
  })
})

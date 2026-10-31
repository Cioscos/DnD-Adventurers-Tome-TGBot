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
})

import { describe, expect, it } from 'vitest'
import type { TFunction } from 'i18next'
import { damageTakenMessage, sharedDamageMessage } from '@/lib/sharedDamage'
import type { CharacterFull } from '@/types'

const t = ((key: string, vars: Record<string, unknown>) => `${key}|${JSON.stringify(vars)}`) as unknown as TFunction
const sheet = (shared: unknown) => ({ shared_damage: shared }) as unknown as CharacterFull

describe('damageTakenMessage', () => {
  it('is null unless the damage was shared', () => {
    expect(damageTakenMessage({ damage_taken: 10 } as unknown as CharacterFull, t)).toBeNull()
  })
  it('says the damage really taken and what the caster took', () => {
    const out = damageTakenMessage({ damage_taken: 10, shared_damage: { amount: 10, caster_name: 'Mira' } } as unknown as CharacterFull, t)
    expect(out).toBe('character.hp.damage_taken_shared|{"n":10,"shared":10,"name":"Mira"}')
  })
})

describe('sharedDamageMessage', () => {
  it('is null without shared damage', () => {
    expect(sharedDamageMessage(sheet(undefined), t)).toBeNull()
  })
  it('reports only the damage when the caster did not roll', () => {
    const out = sharedDamageMessage(sheet({ amount: 10, caster_name: 'Mira', concentration_save: null }), t)
    expect(out?.ok).toBe(true)
    expect(out?.text).toContain('character.hp.shared_damage|')
  })
  it('reports the caster concentration save outcome', () => {
    const save = { total: 7, dc: 10, success: false }
    const lost = sharedDamageMessage(sheet({ amount: 20, caster_name: 'Mira', concentration_save: save }), t)
    expect(lost?.ok).toBe(false)
    expect(lost?.text).toContain('shared_damage_save_fail')
    expect(sharedDamageMessage(sheet({ amount: 20, caster_name: 'Mira', concentration_save: { ...save, success: true } }), t)?.ok).toBe(true)
  })
})

import { describe, expect, it } from 'vitest'
import type { TFunction } from 'i18next'
import { sharedDamageMessage } from '@/lib/sharedDamage'
import type { CharacterFull } from '@/types'

const t = ((key: string, vars: Record<string, unknown>) => `${key}|${JSON.stringify(vars)}`) as unknown as TFunction
const sheet = (shared: unknown) => ({ shared_damage: shared }) as unknown as CharacterFull

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

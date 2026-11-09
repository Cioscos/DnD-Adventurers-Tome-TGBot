import { describe, it, expect } from 'vitest'
import { zeroHpSaveMessage } from '@/lib/zeroHpSave'
import type { CharacterFull } from '@/types'

const t = ((k: string, o: Record<string, unknown>) => `${k}|${o.name}|${o.total}|${o.dc}|${o.hp}`) as never
const char = (save: unknown) => ({
  abilities: [{ feature_key: 'barbarian.relentless_rage', name: 'Ira Implacabile' }], zero_hp_save: save,
} as unknown as CharacterFull)

describe('zeroHpSaveMessage', () => {
  it('says nothing when the blow did not trigger a save', () => {
    expect(zeroHpSaveMessage(char(null), t)).toBeNull()
  })

  it('names the feature and reports success or failure', () => {
    const base = { feature_key: 'barbarian.relentless_rage', ability: 'constitution', die: 12, bonus: 2, total: 14, dc: 10, hp: 1 }
    expect(zeroHpSaveMessage(char({ ...base, success: true }), t)).toEqual({ text: 'character.hp.zero_save_ok|Ira Implacabile|14|10|1', ok: true })
    expect(zeroHpSaveMessage(char({ ...base, success: false, hp: 0 }), t)).toEqual({ text: 'character.hp.zero_save_fail|Ira Implacabile|14|10|0', ok: false })
  })
})

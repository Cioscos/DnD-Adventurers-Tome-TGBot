import { describe, it, expect, vi, beforeEach } from 'vitest'

const { rollOptions, castCheck } = vi.hoisted(() => ({ rollOptions: vi.fn(), castCheck: vi.fn() }))
vi.mock('@/api/client', () => ({ api: { characters: { rollOptions }, spells: { castCheck } } }))

import { prepareCast } from '@/lib/rollOptions'

describe('prepareCast', () => {
  beforeEach(() => {
    rollOptions.mockReset().mockResolvedValue([])
    castCheck.mockReset().mockResolvedValue([])
  })

  it('asks for the cast options at the level of the slot (Twinned Spell costs the level it is cast at)', async () => {
    await prepareCast(3, 9, false, 4)
    expect(rollOptions).toHaveBeenCalledWith(3, { roll: 'cast', spell_id: 9, casting_level: 4 })
  })

  it('does not send a level for a ritual or a cast without a slot', async () => {
    await prepareCast(3, 9, true, 4)
    await prepareCast(3, 9, false, null)
    expect(rollOptions).toHaveBeenNthCalledWith(1, 3, { roll: 'cast', spell_id: 9 })
    expect(rollOptions).toHaveBeenNthCalledWith(2, 3, { roll: 'cast', spell_id: 9 })
  })
})

import { describe, expect, it } from 'vitest'
import { ALL_SLOTS } from '@/lib/equipmentSlots'

describe('caccia: equipaggiamento', () => {
  // caccia: {"id": "CB-003", "fonte": "CLAUDE.md · 11 slot di equipaggiamento", "zona": "flusso:equipaggiamento-ca", "voce": "contratto", "copre": []}
  it('la Mini App conosce gli 11 slot', () => {
    expect([...ALL_SLOTS].sort()).toEqual(
      ['ammunition', 'body', 'cloak', 'feet', 'hands', 'head', 'main_hand', 'neck', 'off_hand', 'ring1', 'ring2'])
  })
})

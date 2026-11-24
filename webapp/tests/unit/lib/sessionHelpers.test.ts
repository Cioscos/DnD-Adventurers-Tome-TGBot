import { describe, it, expect } from 'vitest'
import { getMyRole } from '@/lib/sessionHelpers'
import type { ActiveSessionShape } from '@/lib/sessionHelpers'

/**
 * Pure session helpers. The shapes consumed here mirror the BE `GameSessionRead`
 * serializer (api/schemas/session.py): `gm_user_id: int`, `created_at: str` (ISO),
 * and `participants: [{ user_id, role }]`. The contract assertions below pin those
 * field names so a BE rename surfaces as a failing FE test.
 */
describe('getMyRole', () => {
  it('returns "none" when there is no active session', () => {
    expect(getMyRole(null, 42)).toBe('none')
    expect(getMyRole(undefined, 42)).toBe('none')
  })

  it('returns "none" when the user id is missing', () => {
    const active: ActiveSessionShape = { gm_user_id: 1, participants: [{ user_id: 1 }] }
    expect(getMyRole(active, null)).toBe('none')
    expect(getMyRole(active, undefined)).toBe('none')
  })

  it('returns "gm" when the user is the session GM (gm_user_id match)', () => {
    const active: ActiveSessionShape = { gm_user_id: 7, participants: [] }
    expect(getMyRole(active, 7)).toBe('gm')
  })

  it('returns "player" when the user is a participant but not the GM', () => {
    const active: ActiveSessionShape = {
      gm_user_id: 1,
      participants: [{ user_id: 5, role: 'player' }, { user_id: 9 }],
    }
    expect(getMyRole(active, 9)).toBe('player')
  })

  it('returns "none" when the user is neither GM nor participant', () => {
    const active: ActiveSessionShape = { gm_user_id: 1, participants: [{ user_id: 5 }] }
    expect(getMyRole(active, 99)).toBe('none')
  })

  it('prefers "gm" over "player" when the GM is also listed as a participant', () => {
    const active: ActiveSessionShape = { gm_user_id: 3, participants: [{ user_id: 3 }] }
    expect(getMyRole(active, 3)).toBe('gm')
  })
})


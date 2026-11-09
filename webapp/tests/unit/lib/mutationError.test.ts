import { describe, it, expect, vi, beforeEach } from 'vitest'

const { error } = vi.hoisted(() => ({ error: vi.fn() }))
vi.mock('sonner', () => ({ toast: { error } }))
vi.mock('@/auth/telegram', () => ({ haptic: { error: vi.fn() } }))
vi.mock('@/i18n', () => ({ default: { t: (k: string) => k } }))
vi.mock('@/api/client', () => ({
  ApiError: class ApiError extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))

import { notifyCastError } from '@/lib/mutationError'
import { ApiError } from '@/api/client'

beforeEach(() => error.mockReset())

describe('notifyCastError', () => {
  it('says what the server refused for a rule, not a connection problem', () => {
    notifyCastError(new ApiError(409, { code: 'turn_slot_used' }))
    expect(error).toHaveBeenCalledWith('character.spells.roll_damage.cast_errors.turn_slot_used')
  })

  it('keeps the generic message for anything else', () => {
    notifyCastError(new ApiError(500, { code: 'boom' }))
    expect(error).toHaveBeenCalledWith('common.action_failed')
  })
})

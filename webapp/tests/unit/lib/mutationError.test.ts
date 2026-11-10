import { describe, it, expect, vi, beforeEach } from 'vitest'

const { error } = vi.hoisted(() => ({ error: vi.fn() }))
vi.mock('sonner', () => ({ toast: { error } }))
vi.mock('@/auth/telegram', () => ({ haptic: { error: vi.fn() } }))
vi.mock('@/i18n', () => ({ default: { t: (k: string) => k } }))
vi.mock('@/api/client', () => ({
  ApiError: class ApiError extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))

import { notifyCastError, notifyMutationError } from '@/lib/mutationError'
import { ApiError } from '@/api/client'

beforeEach(() => error.mockReset())

describe('notifyCastError', () => {
  it('says what the server refused for a rule, not a connection problem', () => {
    notifyCastError(new ApiError(409, { code: 'turn_slot_used' }))
    expect(error).toHaveBeenCalledWith('character.spells.roll_damage.cast_errors.turn_slot_used')
  })

  it('keeps the generic message for anything else', () => {
    notifyCastError(new ApiError(500, { code: 'boom' }))
    expect(error).toHaveBeenCalledWith('common.action_refused')
    error.mockReset()
    notifyCastError(new Error('Failed to fetch'))  // il server non ha risposto: solo qui si parla di connessione
    expect(error).toHaveBeenCalledWith('common.action_failed')
  })

  it('gives a dedicated text to a server refusal in the global handler (e.g. Rivivificazione on someone not down)', () => {
    notifyMutationError(new ApiError(409, { code: 'target_not_down' }))
    expect(error).toHaveBeenCalledWith('common.server_errors.target_not_down')
  })

  it('says why Nascondersi was refused instead of the generic text', () => {
    for (const code of ['no_stealth_roll', 'hide_failed', 'incapacitated', 'once_per_turn', 'replace_after_long_rest', 'option_prerequisite', 'option_is_prerequisite']) {
      error.mockReset()
      notifyMutationError(new ApiError(409, { code }))
      expect(error).toHaveBeenCalledWith(`common.server_errors.${code}`)
    }
  })
})

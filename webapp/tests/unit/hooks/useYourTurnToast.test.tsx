import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useYourTurnToast } from '@/hooks/useYourTurnToast'
import type { CombatantLive, EncounterLive } from '@/types'

const { toastSpy } = vi.hoisted(() => ({ toastSpy: vi.fn() }))
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (k: string) => k }) }))
vi.mock('sonner', () => ({ toast: { success: toastSpy } }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))

const c = (id: number, owner: number | null, kind: 'pc' | 'monster' = 'pc'): CombatantLive => ({
  id, kind, owner_user_id: owner, name: `C${id}`, initiative: 10, initiative_die: null,
  initiative_mod: 0, sort_order: id, is_dead: false, conditions: {},
  current_hp: null, max_hp: null, ac: null, hp_bucket: null,
})
const enc = (activeId: number): EncounterLive => ({
  id: 1, mode: 'full', status: 'active', round: 1, active_combatant_id: activeId,
  created_at: '', started_at: null, ended_at: null,
  combatants: [c(1, 99), c(2, null, 'monster'), c(3, 50)],
})

beforeEach(() => toastSpy.mockReset())

describe('useYourTurnToast', () => {
  it('toasts when the active pointer moves to my PC', () => {
    const { rerender } = renderHook(({ e }) => useYourTurnToast(e, 99), { initialProps: { e: enc(2) } })
    expect(toastSpy).not.toHaveBeenCalled()
    rerender({ e: enc(1) })
    expect(toastSpy).toHaveBeenCalledWith('session.combat.your_turn', expect.anything())
  })

  it('does not toast again while I stay the active combatant', () => {
    const { rerender } = renderHook(({ e }) => useYourTurnToast(e, 99), { initialProps: { e: enc(1) } })
    toastSpy.mockReset()
    rerender({ e: enc(1) })
    expect(toastSpy).not.toHaveBeenCalled()
  })

  it("does not toast for someone else's PC", () => {
    const { rerender } = renderHook(({ e }) => useYourTurnToast(e, 99), { initialProps: { e: enc(2) } })
    rerender({ e: enc(3) })
    expect(toastSpy).not.toHaveBeenCalled()
  })
})

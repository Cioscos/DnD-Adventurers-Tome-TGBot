import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import QuickActions from '@/components/character/QuickActions'
import type { CharacterFull } from '@/types'

const { spendHitDice, notifyMutationError, toastError } = vi.hoisted(() => ({
  spendHitDice: vi.fn(),
  notifyMutationError: vi.fn(),
  toastError: vi.fn(),
}))

vi.mock('@/api/client', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, api: { characters: { spendHitDice } } }
})
vi.mock('@/lib/mutationError', () => ({ notifyMutationError }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: toastError, success: vi.fn() }) }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/dice/useDiceAnimation', () => ({ useDiceAnimation: () => ({ playAndCollect: vi.fn() }) }))
vi.mock('@/store/diceSettings', () => ({ useDiceSettings: (sel: (s: { animate3d: boolean }) => unknown) => sel({ animate3d: false }) }))
vi.mock('@/hooks/useReducedMotion', () => ({ useReducedMotion: () => true }))
vi.mock('@/pages/spells/useCastFlow', () => ({ useCastFlow: () => ({ isSpellPending: () => false, beginCast: vi.fn(), dialogs: null }) }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/components/ui/Sheet', () => ({ default: () => null }))
vi.mock('@/components/ui/ConfirmSheet', async () => {
  const React = await import('react')
  return {
    default: (p: { open: boolean; title: string; onConfirm: () => void }) =>
      p.open ? React.createElement('button', { onClick: p.onConfirm }, `confirm:${p.title}`) : null,
  }
})
vi.mock('@/pages/hp/HitDiceResultDialog', () => ({ default: () => null }))
vi.mock('@/components/RollResultModal', () => ({ default: () => null }))
vi.mock('@/components/WeaponAttackModal', () => ({ default: () => null }))

const char = {
  id: 7,
  settings: { quick_actions: [{ type: 'hit_die', classId: 1 }] },
  classes: [{ id: 1, class_name: 'fighter', level: 3, hit_die: 10, hit_dice_used: 0 }],
} as unknown as CharacterFull

async function spendOneHitDie() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
      <QuickActions char={char} />
    </QueryClientProvider>,
  )
  await userEvent.click(screen.getByText('d10 · fighter'))
  await userEvent.click(screen.getByText('confirm:character.quick_actions.spend_hit_die_title'))
}

afterEach(() => { vi.clearAllMocks() })

describe('QuickActions hit die', () => {
  // Un onError proprio esclude l'handler globale: senza avviso restava la sola vibrazione.
  it('warns when spending fails for network reasons', async () => {
    spendHitDice.mockRejectedValue(new TypeError('Failed to fetch'))
    await spendOneHitDie()
    await waitFor(() => expect(notifyMutationError).toHaveBeenCalledTimes(1))
    expect(toastError).not.toHaveBeenCalled()
  })

  it('says the dice are exhausted on a 409, without the generic warning', async () => {
    const { ApiError } = await import('@/api/client')
    spendHitDice.mockRejectedValue(new ApiError(409, 'none left'))
    await spendOneHitDie()
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('character.quick_actions.hit_die_exhausted'))
    expect(notifyMutationError).not.toHaveBeenCalled()
  })
})

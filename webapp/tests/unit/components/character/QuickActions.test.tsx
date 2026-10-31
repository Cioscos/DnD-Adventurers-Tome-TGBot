import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import QuickActions from '@/components/character/QuickActions'
import type { CharacterFull } from '@/types'

const { spendHitDice, update, notifyMutationError, toastError, charges } = vi.hoisted(() => ({
  charges: vi.fn(),
  spendHitDice: vi.fn(),
  update: vi.fn(),
  notifyMutationError: vi.fn(),
  toastError: vi.fn(),
}))

vi.mock('@/api/client', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, api: { characters: { spendHitDice, update }, items: { charges } } }
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
vi.mock('@/components/ui/Sheet', () => ({
  default: (p: { open: boolean; children: unknown }) => (p.open ? p.children : null),
}))
vi.mock('framer-motion', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  const React = await import('react')
  return {
    ...actual,
    Reorder: {
      Group: (p: { values: string[]; onReorder: (v: string[]) => void; children: unknown }) =>
        React.createElement('ul', null,
          React.createElement('button', { onClick: () => p.onReorder([...p.values].reverse()) }, 'test-reorder'),
          p.children),
      Item: (p: { onDragEnd?: () => void; children: unknown }) =>
        React.createElement('li', null,
          React.createElement('button', { onClick: () => p.onDragEnd?.() }, 'test-drop'),
          p.children),
    },
  }
})
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

function renderQC(c: CharacterFull) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
      <QuickActions char={c} />
    </QueryClientProvider>,
  )
}

const autoChar = {
  id: 7,
  settings: {},
  items: [{ id: 10, name: 'Spada', item_type: 'weapon', is_equipped: true }],
  spells: [],
  abilities: [],
  classes: [{ id: 1, class_name: 'fighter', level: 3, hit_die: 10, hit_dice_used: 0 }],
} as unknown as CharacterFull

describe('QuickActions defaults and order', () => {
  it('shows the automatic list for a character without a saved list', () => {
    renderQC(autoChar)
    expect(screen.getByText('Spada')).toBeTruthy()
    expect(screen.getByText('character.quick_actions.rest_short')).toBeTruthy()
  })

  it('shows nothing for an emptied saved list', () => {
    renderQC({ ...autoChar, settings: { quick_actions: [] } } as unknown as CharacterFull)
    expect(screen.queryByText('Spada')).toBeNull()
    expect(screen.getByText('character.quick_actions.empty_hint')).toBeTruthy()
  })

  it('saves the full list on the first change', async () => {
    update.mockResolvedValue(autoChar)
    renderQC(autoChar)
    await userEvent.click(screen.getByLabelText('character.quick_actions.edit'))
    expect(screen.getByText('character.quick_actions.defaults_hint')).toBeTruthy()
    // Toggle off the weapon in the weapons group (not the one in the order list).
    const weaponRow = screen.getAllByText('Spada').map((e) => e.closest('button')).find((b) => b && b.className.includes('min-h-[44px]') && b.className.includes('w-full'))
    await userEvent.click(weaponRow!)
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update.mock.calls[0][1].settings.quick_actions).toEqual([
      { type: 'hit_die', classId: 1 },
      { type: 'rest', rest: 'short' },
      { type: 'counter_inspiration' },
    ])
  })

  it('saves the new order after a reorder', async () => {
    update.mockResolvedValue(autoChar)
    renderQC(autoChar)
    await userEvent.click(screen.getByLabelText('character.quick_actions.edit'))
    await userEvent.click(screen.getByText('test-reorder'))
    await userEvent.click(screen.getAllByText('test-drop')[0])
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update.mock.calls[0][1].settings.quick_actions).toEqual([
      { type: 'counter_inspiration' },
      { type: 'rest', rest: 'short' },
      { type: 'hit_die', classId: 1 },
      { type: 'weapon', id: 10 },
    ])
  })

  it('keeps the new order rendered while the save is pending', async () => {
    let resolveUpdate: (v: CharacterFull) => void = () => {}
    update.mockReturnValue(new Promise<CharacterFull>((r) => { resolveUpdate = r }))
    renderQC(autoChar)
    await userEvent.click(screen.getByLabelText('character.quick_actions.edit'))
    await userEvent.click(screen.getByText('test-reorder'))
    await userEvent.click(screen.getAllByText('test-drop')[0])
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    const order = () => screen.getAllByRole('listitem').map((li) => li.textContent)
    // Ancora in volo: l'ordine nuovo (invertito) non deve tornare al vecchio.
    expect(order()[0]).not.toContain('Spada')
    expect(order()[order().length - 1]).toContain('Spada')
    resolveUpdate(autoChar)
  })

  it('hides restore defaults when the list is not custom', async () => {
    renderQC(autoChar)
    await userEvent.click(screen.getByLabelText('character.quick_actions.edit'))
    expect(screen.queryByText('character.quick_actions.restore_defaults')).toBeNull()
  })

  it('restores defaults by removing the saved list', async () => {
    update.mockResolvedValue(autoChar)
    renderQC({ ...autoChar, settings: { theme: 'x', quick_actions: [] } } as unknown as CharacterFull)
    await userEvent.click(screen.getByLabelText('character.quick_actions.edit'))
    await userEvent.click(screen.getByText('character.quick_actions.restore_defaults'))
    await userEvent.click(screen.getByText('confirm:character.quick_actions.restore_title'))
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update.mock.calls[0][1]).toEqual({ settings: { theme: 'x' } })
  })
})

describe('QuickActions item charges', () => {
  const wandChar = {
    id: 7,
    settings: { quick_actions: [{ type: 'item_charges', id: 5 }] },
    items: [{ id: 5, name: 'Bacchetta', item_type: 'generic', item_metadata: { charges: { max: 7, current: 4, recharge: 'dawn', recharge_amount: 'all' } } }],
    classes: [],
  } as unknown as CharacterFull

  it('decrements the charges through the charges endpoint', async () => {
    charges.mockResolvedValue(wandChar)
    renderQC(wandChar)
    expect(screen.getByText('Bacchetta')).toBeTruthy()
    await userEvent.click(screen.getByLabelText('Bacchetta -1'))
    await waitFor(() => expect(charges).toHaveBeenCalledWith(7, 5, -1))
  })
})

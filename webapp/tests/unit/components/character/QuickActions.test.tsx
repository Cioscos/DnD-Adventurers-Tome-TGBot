import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import QuickActions from '@/components/character/QuickActions'
import { ApiError } from '@/api/client'
import type { CharacterFull } from '@/types'

const { spendHitDice, update, notifyMutationError, toastError, charges, rest } = vi.hoisted(() => ({
  charges: vi.fn(),
  rest: vi.fn(),
  spendHitDice: vi.fn(),
  update: vi.fn(),
  notifyMutationError: vi.fn(),
  toastError: vi.fn(),
}))

vi.mock('@/api/client', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, api: { characters: { spendHitDice, update, rest }, items: { charges } } }
})
vi.mock('@/lib/mutationError', async (orig) => ({ ...(await orig<typeof import('@/lib/mutationError')>()), notifyMutationError }))
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
    default: (p: { open: boolean; title: string; body?: unknown; onConfirm: () => void }) =>
      p.open ? React.createElement('div', null, p.body as never, React.createElement('button', { onClick: p.onConfirm }, `confirm:${p.title}`)) : null,
  }
})
vi.mock('@/pages/hp/HitDiceResultDialog', () => ({ default: () => null }))
vi.mock('@/components/character/RestPreviewList', () => ({ default: () => null }))
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
  await userEvent.click(screen.getByText('d10 · dnd.classes.fighter'))
  await userEvent.click(screen.getByText('confirm:character.quick_actions.spend_hit_die_title'))
}

afterEach(() => { vi.clearAllMocks() })

describe('QuickActions when incapacitated', () => {
  const armed = (incapacitated: boolean) => ({
    id: 7,
    settings: { quick_actions: [{ type: 'weapon', id: 5 }, { type: 'save', ability: 'dexterity' }] },
    classes: [],
    ability_scores: [],
    items: [{ id: 5, name: 'Spada', item_type: 'weapon', item_metadata: {}, is_equipped: true }],
    computed: { incapacitated },
  }) as unknown as CharacterFull

  const show = (c: CharacterFull) => render(
    <QueryClientProvider client={new QueryClient()}>
      <QuickActions char={c} />
    </QueryClientProvider>,
  )

  it('turns off the attack and says why, leaving saves usable', () => {
    show(armed(true))
    expect(screen.getByText('character.turn.incapacitated')).toBeTruthy()
    const buttons = screen.getAllByRole('button') as HTMLButtonElement[]
    expect(buttons.find((b) => b.textContent?.includes('Spada'))?.disabled).toBe(true)
    expect(buttons.find((b) => /dexterity/i.test(b.textContent ?? ''))?.disabled).toBe(false)
  })

  it('keeps the attack usable otherwise', () => {
    show(armed(false))
    expect(screen.queryByText('character.turn.incapacitated')).toBeNull()
    const sword = (screen.getAllByRole('button') as HTMLButtonElement[]).find((b) => b.textContent?.includes('Spada'))
    expect(sword?.disabled).toBe(false)
  })
})

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

describe('QuickActions short rest with Natural Recovery', () => {
  const landDruid = {
    id: 7, settings: { quick_actions: [{ type: 'rest', rest: 'short' }] }, items: [], spells: [], active_states: [],
    classes: [{ id: 1, class_name: 'Druido', level: 5, hit_die: 8, hit_dice_used: 0 }],
    abilities: [{ id: 9, feature_key: 'druid.natural_recovery', uses: 1, max_uses: 1 }],
    spell_slots: [{ id: 1, level: 1, total: 4, used: 3, available: 1, is_pact: false }],
  } as unknown as CharacterFull

  it('offers the picker and sends the chosen slots with the rest', async () => {
    rest.mockResolvedValue(landDruid)
    renderQC(landDruid)
    await userEvent.click(screen.getByText('character.quick_actions.rest_short'))
    expect(screen.getByTestId('natural-recovery')).toBeTruthy()
    await userEvent.click(within(screen.getByTestId('nr-plus-1')).getByRole('button'))
    await userEvent.click(screen.getByText('character.hp.confirm_rest'))
    await waitFor(() => expect(rest).toHaveBeenCalledWith(7, 'short', expect.objectContaining({ natural_recovery: { 1: 1 } })))
  })

  it('rests without the field when nothing was chosen', async () => {
    rest.mockResolvedValue(landDruid)
    renderQC(landDruid)
    await userEvent.click(screen.getByText('character.quick_actions.rest_short'))
    await userEvent.click(screen.getByText('character.hp.confirm_rest'))
    await waitFor(() => expect(rest).toHaveBeenCalledWith(7, 'short', expect.objectContaining({ interrupted: false, ate_and_drank: true })))
  })
})

describe('QuickActions long rest questions (same as the menu)', () => {
  const longChar = {
    id: 7, settings: { quick_actions: [{ type: 'rest', rest: 'long' }] }, items: [], spells: [], active_states: [], rules_edition: '2014',
    classes: [{ id: 1, class_name: 'fighter', level: 3, hit_die: 10, hit_dice_used: 0 }],
  } as unknown as CharacterFull

  it('asks about interruption and food, and confirms a too-soon long rest', async () => {
    rest.mockRejectedValueOnce(new ApiError(409, 'long_rest_too_soon')).mockResolvedValue(longChar)
    renderQC(longChar)
    await userEvent.click(screen.getByText('character.quick_actions.rest_long'))
    const switches = screen.getAllByRole('switch')
    expect(switches).toHaveLength(2)
    await userEvent.click(switches[0])
    await userEvent.click(screen.getByText('confirm:character.quick_actions.confirm_long_rest_title'))
    await waitFor(() => expect(rest).toHaveBeenCalledWith(7, 'long', expect.objectContaining({ interrupted: true, ate_and_drank: true })))
    await screen.findByText('character.quick_actions.rest_too_soon_body')
    await userEvent.click(screen.getByText('confirm:character.quick_actions.rest_too_soon_title'))
    await waitFor(() => expect(rest).toHaveBeenLastCalledWith(7, 'long', expect.objectContaining({ confirm_early: true })))
  })
})

describe('QuickActions long rest with the Pact of the Tome', () => {
  const tomeLock = {
    id: 7, settings: { quick_actions: [{ type: 'rest', rest: 'long' }] }, items: [], spells: [], active_states: [], rules_edition: '2024',
    classes: [{ id: 1, class_name: 'warlock', level: 3, hit_die: 8, hit_dice_used: 0 }],
    abilities: [{ id: 5, feature_key: 'warlock.pact_of_the_tome', name: 'Patto del Tomo' }],
  } as unknown as CharacterFull

  it('offers the switch and sends reopen_tome with the long rest', async () => {
    rest.mockResolvedValue(tomeLock)
    renderQC(tomeLock)
    await userEvent.click(screen.getByText('character.quick_actions.rest_long'))
    await userEvent.click(within(screen.getByTestId('tome-reopen')).getByRole('switch'))
    await userEvent.click(screen.getByText('confirm:character.quick_actions.confirm_long_rest_title'))
    await waitFor(() => expect(rest).toHaveBeenCalledWith(7, 'long', expect.objectContaining({ reopen_tome: true })))
  })

  it('does not offer it to a character without the pact', async () => {
    renderQC({ ...tomeLock, abilities: [] } as unknown as CharacterFull)
    await userEvent.click(screen.getByText('character.quick_actions.rest_long'))
    expect(screen.queryByTestId('tome-reopen')).toBeNull()
  })
})

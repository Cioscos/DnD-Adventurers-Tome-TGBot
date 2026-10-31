import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import RestSheet from '@/components/character/RestSheet'
import type { CharacterFull } from '@/types'

const { spendHitDice, rest, restPreview, notifyMutationError, toastError, toastSuccess } = vi.hoisted(() => ({
  spendHitDice: vi.fn(),
  rest: vi.fn(),
  restPreview: vi.fn(),
  notifyMutationError: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}))

vi.mock('@/dice/useAnimatedRoll', () => ({ useAnimatedRoll: () => async () => undefined }))
vi.mock('@/api/client', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, api: { characters: { spendHitDice, rest, restPreview } } }
})
vi.mock('@/lib/mutationError', () => ({ notifyMutationError }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: toastError, success: toastSuccess }) }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
vi.mock('@/components/ui/ConfirmSheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; body?: unknown }) => (p.open ? React.createElement('div', null, p.body) : null) }
})
vi.mock('@/pages/hp/HitDiceModal', async () => {
  const React = await import('react')
  return {
    default: (p: { onSpend: (classId: number, count: number) => void; onConfirmRest: () => void; preview?: unknown }) =>
      React.createElement('div', { 'data-testid': 'hit-dice-modal' },
        React.createElement('button', { onClick: () => p.onSpend(1, 2) }, 'spend'),
        React.createElement('button', { onClick: p.onConfirmRest }, 'rest'),
        p.preview),
  }
})
vi.mock('@/pages/hp/HitDiceResultDialog', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'hit-die-result' }) }
})

const char = { id: 7, classes: [{ id: 1, class_name: 'fighter', level: 3 }] } as unknown as CharacterFull

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const onClose = vi.fn()
  render(
    <QueryClientProvider client={qc}>
      <RestSheet char={char} open onClose={onClose} />
    </QueryClientProvider>,
  )
  return { qc, onClose }
}

const openShortRest = () => userEvent.click(screen.getByText('character.quick_actions.rest_short'))

afterEach(() => { vi.clearAllMocks() })

describe('RestSheet short rest', () => {
  it('spends hit dice and shows the result', async () => {
    spendHitDice.mockResolvedValue({ rolls: [4] })
    setup()
    await openShortRest()
    await userEvent.click(screen.getByText('spend'))
    await waitFor(() => expect(spendHitDice).toHaveBeenCalledWith(7, 1, 2, undefined))
    expect(await screen.findByTestId('hit-die-result')).toBeTruthy()
    expect(notifyMutationError).not.toHaveBeenCalled()
  })

  it('confirming the rest updates the sheet and closes', async () => {
    const updated = { ...char, current_hit_points: 9 }
    rest.mockResolvedValue(updated)
    const { qc, onClose } = setup()
    await openShortRest()
    await userEvent.click(screen.getByText('rest'))
    await waitFor(() => expect(rest).toHaveBeenCalledWith(7, 'short'))
    await waitFor(() => expect(onClose).toHaveBeenCalled())
    expect(qc.getQueryData(['character', 7])).toEqual(updated)
    expect(toastSuccess).toHaveBeenCalledWith('character.quick_actions.rest_done')
    expect(screen.queryByTestId('hit-dice-modal')).toBeNull()
  })

  // Un onError proprio esclude l'handler globale: senza avviso restava la sola vibrazione.
  it('warns when spending a hit die fails for network reasons', async () => {
    spendHitDice.mockRejectedValue(new TypeError('Failed to fetch'))
    setup()
    await openShortRest()
    await userEvent.click(screen.getByText('spend'))
    await waitFor(() => expect(notifyMutationError).toHaveBeenCalledTimes(1))
    expect(toastError).not.toHaveBeenCalled()
  })

  it('says the dice are exhausted on a 409, without the generic warning', async () => {
    const { ApiError } = await import('@/api/client')
    spendHitDice.mockRejectedValue(new ApiError(409, 'none left'))
    setup()
    await openShortRest()
    await userEvent.click(screen.getByText('spend'))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('character.quick_actions.hit_die_exhausted'))
    expect(notifyMutationError).not.toHaveBeenCalled()
  })
})

describe('RestSheet preview', () => {
  const preview = {
    hp_gain: 12, hit_dice_regain: { '1': 2 }, slots: { '1': 3 }, pact_slots: 0, abilities: ['Furia'],
    homebrew_resources: [], item_charges: ['Bacchetta: +1d6+1'], exhaustion_change: -1, ends_concentration: true,
  }

  it('shows what a long rest recovers before confirming', async () => {
    restPreview.mockResolvedValue(preview)
    setup()
    await userEvent.click(screen.getByText('character.quick_actions.rest_long'))
    expect(await screen.findByText('+12')).toBeTruthy()
    expect(screen.getByText('Furia')).toBeTruthy()
    expect(screen.getByText('Bacchetta: +1d6+1')).toBeTruthy()
    expect(screen.getByText('character.rest_preview.concentration')).toBeTruthy()
    expect(restPreview).toHaveBeenCalledWith(7, 'long')
    expect(rest).not.toHaveBeenCalled()
  })

  it('asks the short preview when opening the short rest', async () => {
    restPreview.mockResolvedValue({ ...preview, hp_gain: 0, slots: {}, hit_dice_regain: {} })
    setup()
    await openShortRest()
    await waitFor(() => expect(restPreview).toHaveBeenCalledWith(7, 'short'))
  })
})

import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import RestSheet from '@/components/character/RestSheet'
import type { CharacterFull } from '@/types'

const { spendHitDice, rest, restPreview, notifyMutationError, toastError, toastSuccess, featureUse, endActiveState } = vi.hoisted(() => ({
  featureUse: vi.fn(),
  endActiveState: vi.fn(),
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
  return { ...actual, api: { characters: { spendHitDice, rest, restPreview, featureUse, endActiveState } } }
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

function setup(c: CharacterFull = char) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const onClose = vi.fn()
  render(
    <QueryClientProvider client={qc}>
      <RestSheet char={c} open onClose={onClose} />
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
    await waitFor(() => expect(rest).toHaveBeenCalledWith(7, 'short', {
      interrupted: false, ate_and_drank: true, confirm_early: undefined }))
    await waitFor(() => expect(onClose).toHaveBeenCalled())
    expect(qc.getQueryData(['character', 7])).toEqual(updated)
    expect(toastSuccess).toHaveBeenCalledWith('character.quick_actions.rest_done')
    expect(screen.queryByTestId('hit-dice-modal')).toBeNull()
  })

  it('2024: offers the interrupted question and sends it', async () => {
    rest.mockResolvedValue(char)
    setup({ ...char, rules_edition: '2024' } as CharacterFull)
    await openShortRest()
    await userEvent.click(screen.getByRole('switch'))
    await userEvent.click(screen.getByText('rest'))
    await waitFor(() => expect(rest).toHaveBeenCalledWith(7, 'short', {
      interrupted: true, ate_and_drank: true, confirm_early: undefined }))
  })

  it('2014: no interrupted question on the short rest', async () => {
    setup({ ...char, rules_edition: '2014' } as CharacterFull)
    await openShortRest()
    expect(screen.queryByRole('switch')).toBeNull()
  })

  describe('Song of Rest switch (bard)', () => {
    const bard = { id: 7, classes: [{ id: 1, class_name: 'bard', level: 3 }], active_states: [],
      abilities: [{ id: 4, feature_key: 'bard.song_of_rest', name: 'Canto di Riposo', has_on_use: true }] } as unknown as CharacterFull

    it('is offered only to a bard and starts the song for the rest', async () => {
      featureUse.mockResolvedValue({ rolls: [], state: { key: 'song_of_rest' } })
      setup()
      await openShortRest()
      expect(screen.queryByRole('switch')).toBeNull()
      vi.clearAllMocks()
      setup(bard)
      await userEvent.click(screen.getAllByText('character.quick_actions.rest_short').at(-1) as HTMLElement)
      await userEvent.click(screen.getByRole('switch'))
      await waitFor(() => expect(featureUse).toHaveBeenCalledWith(7, 'bard.song_of_rest'))
    })

    it('shows the song as on when it is already active and turns it off', async () => {
      endActiveState.mockResolvedValue([])
      setup({ ...bard, active_states: [{ key: 'song_of_rest', feature_key: 'bard.song_of_rest' }] } as unknown as CharacterFull)
      await openShortRest()
      expect(screen.getByRole('switch')).toBeChecked()
      await userEvent.click(screen.getByRole('switch'))
      await waitFor(() => expect(endActiveState).toHaveBeenCalledWith(7, 'song_of_rest'))
    })
  })

  it('a refused rest at 0 HP warns instead of the generic error', async () => {
    const { ApiError } = await import('@/api/client')
    rest.mockRejectedValue(new ApiError(409, 'rest_needs_hp'))
    setup()
    await openShortRest()
    await userEvent.click(screen.getByText('rest'))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('character.quick_actions.rest_needs_hp'))
    expect(notifyMutationError).not.toHaveBeenCalled()
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
    homebrew_resources: [], item_charges: [{ name: 'Bacchetta', gain: null, formula: '1d6+1', full: false }], exhaustion_change: -1, ends_concentration: true,
  }

  it('shows what a long rest recovers before confirming', async () => {
    restPreview.mockResolvedValue(preview)
    setup()
    await userEvent.click(screen.getByText('character.quick_actions.rest_long'))
    expect(await screen.findByText('+12')).toBeTruthy()
    expect(screen.getByText('Furia')).toBeTruthy()
    expect(screen.getByText('+1d6+1')).toBeTruthy()
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

const btn = (id: string) => within(screen.getByTestId(id)).getByRole('button')

describe('Natural Recovery (druid, Circle of the Land)', () => {
  const druid = (uses = 1, level = 5) => ({
    id: 7, classes: [{ id: 1, class_name: 'Druido', level }], active_states: [],
    abilities: [{ id: 9, feature_key: 'druid.natural_recovery', uses, max_uses: 1 }],
    spell_slots: [
      { id: 1, level: 1, total: 4, used: 3, available: 1, is_pact: false },
      { id: 2, level: 2, total: 3, used: 1, available: 2, is_pact: false },
      { id: 3, level: 3, total: 2, used: 0, available: 2, is_pact: false },
      { id: 4, level: 1, total: 2, used: 2, available: 0, is_pact: true },
    ],
  }) as unknown as CharacterFull

  it('is not offered without the feature, without a use left or without spent slots', async () => {
    setup()
    await openShortRest()
    expect(screen.queryByTestId('natural-recovery')).toBeNull()
    vi.clearAllMocks()
    setup(druid(0))
    await userEvent.click(screen.getAllByText('character.quick_actions.rest_short').at(-1) as HTMLElement)
    expect(screen.queryByTestId('natural-recovery')).toBeNull()
  })

  it('lets the player pick spent slots up to half the druid level (rounded up) and sends them with the rest', async () => {
    rest.mockResolvedValue(druid())
    setup(druid())
    await openShortRest()
    expect(screen.getByTestId('natural-recovery')).toBeTruthy()
    expect(screen.getByTestId('nr-left')).toHaveTextContent('3')  // livello 5: metà per eccesso = 3
    await userEvent.click(btn('nr-plus-1'))
    await userEvent.click(btn('nr-plus-1'))
    expect(screen.getByTestId('nr-count-1')).toHaveTextContent('2')
    expect(screen.getByTestId('nr-left')).toHaveTextContent('1')
    expect(btn('nr-plus-2')).toBeDisabled()  // un livello 2 costa più di quello che resta
    await userEvent.click(btn('nr-minus-1'))
    await userEvent.click(btn('nr-plus-2'))
    expect(btn('nr-plus-2')).toBeDisabled()  // spesi: uno solo
    await userEvent.click(screen.getByText('rest'))
    await waitFor(() => expect(rest).toHaveBeenCalledWith(7, 'short', expect.objectContaining({ natural_recovery: { 1: 1, 2: 1 } })))
  })

  it('offers only the spent normal slots of 5th level or lower, never the pact slots', async () => {
    setup(druid())
    await openShortRest()
    expect(screen.getByTestId('nr-plus-1')).toBeTruthy()
    expect(screen.getByTestId('nr-plus-2')).toBeTruthy()
    expect(screen.queryByTestId('nr-plus-3')).toBeNull()  // nessuno spento al 3°
  })

  it('does not send a recovery when nothing was chosen', async () => {
    rest.mockResolvedValue(druid())
    setup(druid())
    await openShortRest()
    await userEvent.click(screen.getByText('rest'))
    await waitFor(() => expect(rest).toHaveBeenCalled())
    expect(rest.mock.calls[0][2].natural_recovery).toBeUndefined()
  })
})

describe('Arcane Recovery (wizard)', () => {
  const wizard = (uses = 1, level = 4) => ({
    id: 7, classes: [{ id: 1, class_name: 'Mago', level }], active_states: [],
    abilities: [{ id: 9, feature_key: 'wizard.arcane_recovery', uses, max_uses: 1 }],
    spell_slots: [
      { id: 1, level: 1, total: 4, used: 3, available: 1, is_pact: false },
      { id: 2, level: 2, total: 3, used: 1, available: 2, is_pact: false },
    ],
  }) as unknown as CharacterFull

  it('is offered to a wizard with a use left, with a budget of half the wizard level (rounded up)', async () => {
    setup(wizard())
    await openShortRest()
    expect(screen.getByTestId('arcane-recovery')).toBeTruthy()
    expect(screen.queryByTestId('natural-recovery')).toBeNull()
    expect(screen.getByTestId('ar-left')).toHaveTextContent('2')
  })

  it('is hidden once the daily use is spent', async () => {
    setup(wizard(0))
    await openShortRest()
    expect(screen.queryByTestId('arcane-recovery')).toBeNull()
  })

  it('sends the chosen slots as arcane_recovery, not natural_recovery', async () => {
    rest.mockResolvedValue(wizard())
    setup(wizard())
    await openShortRest()
    await userEvent.click(within(screen.getByTestId('ar-plus-2')).getByRole('button'))
    expect(within(screen.getByTestId('ar-plus-2')).getByRole('button')).toBeDisabled()
    await userEvent.click(screen.getByText('rest'))
    await waitFor(() => expect(rest).toHaveBeenCalledWith(7, 'short', expect.objectContaining({ arcane_recovery: { 2: 1 } })))
    expect(rest.mock.calls[0][2].natural_recovery).toBeUndefined()
  })
})

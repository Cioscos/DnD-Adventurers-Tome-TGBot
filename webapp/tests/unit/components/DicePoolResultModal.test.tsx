import { describe, it, expect, vi, afterEach } from 'vitest'
import type { ReactNode } from 'react'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import DicePoolResultModal from '@/components/DicePoolResultModal'
import { ApiError } from '@/api/client'

// --- Spies shared with the hoisted factories ---------------------------------
const { diceResult, toastError } = vi.hoisted(() => ({
  diceResult: vi.fn(),
  toastError: vi.fn(),
}))

// api.dice.result is the single endpoint this modal hits (FE↔API contract under
// test). ApiError must be the SAME class the SUT checks `instanceof` against, so
// it is defined here and re-imported by the test for the 409 case.
vi.mock('@/api/client', () => ({
  api: { dice: { result: diceResult } },
  ApiError: class ApiError extends Error {
    status: number
    constructor(status: number, message = '') {
      super(message)
      this.status = status
    }
  },
}))

// animate3d=false → the mutation takes the Math.random path (no 3D animation),
// keeping the reroll deterministic and free of the dice canvas.
vi.mock('@/store/diceSettings', () => ({
  useDiceSettings: (sel: (s: { animate3d: boolean }) => unknown) => sel({ animate3d: false }),
}))
vi.mock('@/dice/useDiceAnimation', () => ({
  useDiceAnimation: () => ({ playAndCollect: () => Promise.resolve([]) }),
}))
vi.mock('@/hooks/useReducedMotion', () => ({ useReducedMotion: () => false }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: toastError }) }))
vi.mock('@/auth/telegram', () => ({ haptic: { success: () => {}, error: () => {} } }))

vi.mock('@/components/ui/ResultDialog', async () => {
  const React = await import('react')
  return {
    default: (p: { title?: ReactNode; subtitle?: ReactNode; extraActions?: ReactNode; children?: ReactNode }) =>
      React.createElement(
        'div',
        { 'data-testid': 'result-dialog' },
        p.subtitle ? React.createElement('div', { 'data-testid': 'rd-subtitle' }, p.subtitle) : null,
        p.extraActions ? React.createElement('div', { 'data-testid': 'rd-extra' }, p.extraActions) : null,
        React.createElement('div', { 'data-testid': 'rd-body' }, p.children),
      ),
  }
})
vi.mock('@/components/InspirationRerollButton', async () => {
  const React = await import('react')
  return {
    default: (p: { available?: boolean; pending?: boolean; onClick: () => void }) =>
      p.available === false
        ? null
        : React.createElement(
            'button',
            { 'data-testid': 'inspiration-reroll', disabled: p.pending, onClick: p.onClick },
            'reroll',
          ),
  }
})

type RollGroup = { kind: 'd4' | 'd6' | 'd8' | 'd10' | 'd12' | 'd20'; notation: string; rolls: number[]; total: number }

afterEach(() => {
  vi.restoreAllMocks()
  diceResult.mockReset()
  toastError.mockReset()
})

describe('DicePoolResultModal', () => {
  it('renders a single d20 group and offers the inspiration reroll on a pure d20 pool', () => {
    const group: RollGroup = { kind: 'd20', notation: '1d20', rolls: [15], total: 15 }
    renderWithProviders(
      <DicePoolResultModal charId={7} initialResults={[group]} inspirationAvailable onClose={() => {}} />,
    )
    expect(screen.getByText('1d20')).toBeInTheDocument()
    expect(screen.getByText('15')).toBeInTheDocument()
    expect(screen.getByTestId('inspiration-reroll')).toBeInTheDocument()
  })

  it('shows a combined total and hides the reroll button for a multi-group pool', () => {
    const g1: RollGroup = { kind: 'd20', notation: '1d20', rolls: [10], total: 10 }
    const g2: RollGroup = { kind: 'd6', notation: '1d6', rolls: [4], total: 4 }
    renderWithProviders(
      <DicePoolResultModal charId={7} initialResults={[g1, g2]} inspirationAvailable onClose={() => {}} />,
    )
    expect(screen.getByText(/Totale:/)).toBeInTheDocument()
    expect(screen.getByText('14')).toBeInTheDocument() // 10 + 4
    expect(screen.queryByTestId('inspiration-reroll')).not.toBeInTheDocument() // not a pure d20 pool
  })

  it('rerolls via api.dice.result with the exact DiceResultRequest payload, then locks the button', async () => {
    // floor(0.55 * 20) + 1 = 12
    vi.spyOn(Math, 'random').mockReturnValue(0.55)
    diceResult.mockResolvedValue({ notation: '1d20', rolls: [12], total: 12 })

    const group: RollGroup = { kind: 'd20', notation: '1d20', rolls: [3], total: 3 }
    renderWithProviders(
      <DicePoolResultModal charId={7} initialResults={[group]} inspirationAvailable onClose={() => {}} />,
    )
    await userEvent.click(screen.getByTestId('inspiration-reroll'))

    await waitFor(() => expect(diceResult).toHaveBeenCalledTimes(1))
    // Contract: body matches DiceResultRequestBody (FE) === DiceResultRequest (BE).
    expect(diceResult).toHaveBeenCalledWith(7, {
      rolls: [{ kind: 'd20', value: 12 }],
      notation: '1d20',
      with_inspiration: true,
    })
    // wasRerolled → reroll button gone, new die value shown.
    await waitFor(() => expect(screen.queryByTestId('inspiration-reroll')).not.toBeInTheDocument())
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByTestId('rd-subtitle')).toBeInTheDocument() // reroll badge
  })

  it('surfaces a toast error when the reroll is rejected with 409 (inspiration unavailable)', async () => {
    vi.spyOn(Math, 'random').mockReturnValue(0.1)
    diceResult.mockRejectedValue(new ApiError(409))

    const group: RollGroup = { kind: 'd20', notation: '1d20', rolls: [3], total: 3 }
    renderWithProviders(
      <DicePoolResultModal charId={7} initialResults={[group]} inspirationAvailable onClose={() => {}} />,
    )
    await userEvent.click(screen.getByTestId('inspiration-reroll'))

    await waitFor(() => expect(toastError).toHaveBeenCalledTimes(1))
    // The pool is unchanged on failure; the button stays available.
    expect(screen.getByTestId('inspiration-reroll')).toBeInTheDocument()
  })
})

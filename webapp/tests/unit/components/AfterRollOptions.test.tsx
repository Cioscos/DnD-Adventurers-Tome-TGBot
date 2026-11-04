import { useState } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import RollResultModal from '@/components/RollResultModal'
import { renderWithProviders } from '../utils/renderWithProviders'
import type { RollOption } from '@/api/client'

const { rollOptions, lastRollOptions, lastRollRefund, rollD20 } = vi.hoisted(() => ({
  rollOptions: vi.fn(), lastRollOptions: vi.fn(), lastRollRefund: vi.fn(), rollD20: vi.fn(),
}))
vi.mock('@/api/client', () => ({
  api: { characters: { rollOptions, lastRollOptions, lastRollRefund } },
  ApiError: class extends Error {},
}))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/hooks/useD20Roll', async (orig) => ({ ...(await orig() as object), useD20Roll: () => rollD20 }))
vi.mock('@/hooks/useRollNoteLabels', () => ({ useRollNoteLabels: () => (notes: string[]) => notes }))

const option = (over: Partial<RollOption>): RollOption => ({
  key: 'add', phase: 'after_roll', label: 'Aggiungi 1d10?', source: 'feature:x', dice: '1d10', bonus: null, mode: null,
  multiplier: null, once_per_turn: false, slot: null, needs: null, requires_input: null, input_options: [],
  auto_fail: false, cost: null, group: null, dice_cost: 0, after: 'add', pay_if_success: false, saved_dice: [], ...over,
})
const ROLL = { die: 5, bonus: 2, total: 7, is_critical: false, is_fumble: false }
const QUERY = { roll: 'skill', skill: 'athletics' } as const

function modal(result = ROLL) {
  return renderWithProviders(
    <RollResultModal result={result} title="Atletica" onClose={() => undefined} afterRoll={{ charId: 1, query: QUERY }} />,
  )
}

describe('AfterRollOptions nel modale di esito', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    rollD20.mockResolvedValue(undefined)
  })

  it('non blocca: nessun pulsante senza opzioni, e ignora le altre fasi', async () => {
    rollOptions.mockResolvedValue([option({ key: 'x', phase: 'before', label: 'Prima?', after: null })])
    modal()
    await waitFor(() => expect(rollOptions).toHaveBeenCalledWith(1, QUERY))
    expect(screen.queryByText('Prima?')).toBeNull()
    expect(lastRollOptions).not.toHaveBeenCalled()
  })

  it('una somma aggiorna il totale, senza tirare il d20', async () => {
    rollOptions.mockResolvedValue([option({})])
    lastRollOptions.mockResolvedValue({ ...ROLL, bonus: 2, total: 13 })
    modal()
    await userEvent.click(await screen.findByRole('button', { name: /Aggiungi 1d10\?/ }))
    expect(await screen.findByText('13')).toBeInTheDocument()
    expect(rollD20).not.toHaveBeenCalled()
    expect(lastRollOptions).toHaveBeenCalledWith(1, { options: ['add'], option_inputs: {}, mode: 'normal', dice: undefined })
  })

  it('un ritiro anima il d20 col modo dell\'opzione e manda le facce', async () => {
    rollOptions.mockResolvedValue([option({ key: 'again', label: 'Ritira?', after: 'reroll', dice: null, mode: 'advantage' })])
    rollD20.mockResolvedValue([3, 18])
    lastRollOptions.mockResolvedValue({ ...ROLL, die: 18, dice: [3, 18], mode: 'advantage', total: 20 })
    modal()
    await userEvent.click(await screen.findByRole('button', { name: /Ritira\?/ }))
    expect(await screen.findByText('20')).toBeInTheDocument()
    expect(rollD20).toHaveBeenCalledWith('advantage')
    expect(lastRollOptions).toHaveBeenCalledWith(1, { options: ['again'], option_inputs: {}, mode: 'advantage', dice: [3, 18] })
  })

  it('pay_if_success: «No» rimborsa, una volta sola', async () => {
    rollOptions.mockResolvedValue([option({ pay_if_success: true })])
    lastRollOptions.mockResolvedValue({ ...ROLL, total: 12, refundable: ['add'] })
    lastRollRefund.mockResolvedValue({})
    modal()
    await userEvent.click(await screen.findByRole('button', { name: /Aggiungi 1d10\?/ }))
    await screen.findByText('character.roll_options.succeeded_question')
    await userEvent.click(screen.getByRole('button', { name: 'common.no' }))
    await waitFor(() => expect(lastRollRefund).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(screen.queryByText('character.roll_options.succeeded_question')).toBeNull())
  })

  it('pay_if_success: «Sì» non rimborsa', async () => {
    rollOptions.mockResolvedValue([option({ pay_if_success: true })])
    lastRollOptions.mockResolvedValue({ ...ROLL, total: 12, refundable: ['add'] })
    modal()
    await userEvent.click(await screen.findByRole('button', { name: /Aggiungi 1d10\?/ }))
    await userEvent.click(await screen.findByRole('button', { name: 'common.yes' }))
    expect(screen.queryByText('character.roll_options.succeeded_question')).toBeNull()
    expect(lastRollRefund).not.toHaveBeenCalled()
  })

  it('con un fallimento automatico non offre nulla', async () => {
    rollOptions.mockResolvedValue([option({})])
    modal({ ...ROLL, auto_fail: true } as typeof ROLL)
    await screen.findByText('7')
    expect(rollOptions).not.toHaveBeenCalled()
  })

  it('un nuovo risultato dal genitore (ispirazione) sostituisce quello ritoccato', async () => {
    rollOptions.mockResolvedValue([option({})])
    lastRollOptions.mockResolvedValue({ ...ROLL, total: 13 })
    function Parent() {
      const [result, setResult] = useState(ROLL)
      return (
        <>
          <button onClick={() => setResult({ ...ROLL, die: 9, total: 11 })}>nuovo tiro</button>
          <RollResultModal result={result} title="Atletica" onClose={() => undefined} afterRoll={{ charId: 1, query: QUERY }} />
        </>
      )
    }
    renderWithProviders(<Parent />)
    await userEvent.click(await screen.findByRole('button', { name: /Aggiungi 1d10\?/ }))
    await screen.findByText('13')
    await userEvent.click(screen.getByText('nuovo tiro'))
    expect(await screen.findByText('11')).toBeInTheDocument()
  })
})

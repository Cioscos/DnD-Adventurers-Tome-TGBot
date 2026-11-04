import { useState } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import RollResultModal from '@/components/RollResultModal'
import { RefundQuestionHost } from '@/components/rules/AfterRollOptions'
import { usePromptStore } from '@/lib/rollOptions'
import { renderWithProviders } from '../utils/renderWithProviders'
import type { RollOption } from '@/api/client'

const { rollOptions, lastRollOptions, lastRollRefund, rollD20, turnState } = vi.hoisted(() => ({
  rollOptions: vi.fn(), lastRollOptions: vi.fn(), lastRollRefund: vi.fn(), rollD20: vi.fn(), turnState: vi.fn(),
}))
vi.mock('@/api/client', () => ({
  api: { characters: { rollOptions, lastRollOptions, lastRollRefund, turnState } },
  ApiError: class extends Error {},
}))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/hooks/useD20Roll', async (orig) => ({ ...(await orig() as object), useD20Roll: () => rollD20 }))
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})
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

  it('pay_if_success: «Sì» chiude la domanda sul server, tenendo il pagamento', async () => {
    rollOptions.mockResolvedValue([option({ pay_if_success: true })])
    lastRollOptions.mockResolvedValue({ ...ROLL, total: 12, refundable: ['add'] })
    lastRollRefund.mockResolvedValue({})
    modal()
    await userEvent.click(await screen.findByRole('button', { name: /Aggiungi 1d10\?/ }))
    await userEvent.click(await screen.findByRole('button', { name: 'common.yes' }))
    await waitFor(() => expect(lastRollRefund).toHaveBeenCalledWith(1, true))
    await waitFor(() => expect(screen.queryByText('character.roll_options.succeeded_question')).toBeNull())
  })

  it('un\'opzione usata sparisce per questo tiro e torna sul tiro nuovo', async () => {
    rollOptions.mockResolvedValue([option({}), option({ key: 'b', label: 'Altra?' })])
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
    expect(screen.queryByRole('button', { name: /Aggiungi 1d10\?/ })).toBeNull()
    expect(screen.getByRole('button', { name: /Altra\?/ })).toBeInTheDocument()
    await userEvent.click(screen.getByText('nuovo tiro'))
    expect(await screen.findByRole('button', { name: /Aggiungi 1d10\?/ })).toBeInTheDocument()
  })

  it('l\'ispirazione durante la domanda la chiude, senza rimborsi né 409', async () => {
    rollOptions.mockResolvedValue([option({ pay_if_success: true })])
    lastRollOptions.mockResolvedValue({ ...ROLL, total: 12, refundable: ['add'] })
    function Parent() {
      const [result, setResult] = useState(ROLL)
      return (
        <>
          <button onClick={() => setResult({ ...ROLL, die: 9, total: 11 })}>ispirazione</button>
          <RollResultModal result={result} title="Atletica" onClose={() => undefined} afterRoll={{ charId: 1, query: QUERY }} />
        </>
      )
    }
    renderWithProviders(<Parent />)
    await userEvent.click(await screen.findByRole('button', { name: /Aggiungi 1d10\?/ }))
    await screen.findByText('character.roll_options.succeeded_question')
    await userEvent.click(screen.getByText('ispirazione'))
    await waitFor(() => expect(screen.queryByText('character.roll_options.succeeded_question')).toBeNull())
    expect(lastRollRefund).not.toHaveBeenCalled()
  })

  it('un 409 sul rimborso chiude la domanda: il tiro non è più l\'ultimo', async () => {
    rollOptions.mockResolvedValue([option({ pay_if_success: true })])
    lastRollOptions.mockResolvedValue({ ...ROLL, total: 12, refundable: ['add'] })
    lastRollRefund.mockRejectedValue(Object.assign(new Error('409'), { status: 409 }))
    modal()
    await userEvent.click(await screen.findByRole('button', { name: /Aggiungi 1d10\?/ }))
    await userEvent.click(await screen.findByRole('button', { name: 'common.no' }))
    await waitFor(() => expect(screen.queryByText('character.roll_options.succeeded_question')).toBeNull())
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

describe('RefundQuestionHost', () => {
  const pending = { turn: { last_roll: { total: 16, refundable: { add: ['feature:x:1'] } } } }
  const host = (path = '/char/1/skills') => renderWithProviders(
    <RefundQuestionHost />, { route: path },
  )

  beforeEach(() => {
    vi.clearAllMocks()
    usePromptStore.setState({ request: null })
  })

  it('ripropone la domanda rimasta senza risposta, anche dopo aver chiuso il modale', async () => {
    turnState.mockResolvedValue(pending)
    lastRollRefund.mockResolvedValue({})
    host()
    await screen.findByText('character.roll_options.succeeded_question')
    turnState.mockResolvedValue({ turn: {} })
    await userEvent.click(screen.getByRole('button', { name: 'common.no' }))
    await waitFor(() => expect(lastRollRefund).toHaveBeenCalledWith(1, false))
    await waitFor(() => expect(screen.queryByText('character.roll_options.succeeded_question')).toBeNull())
  })

  it('tace se non resta nulla da chiedere, se il prompt è aperto e fuori dal personaggio', async () => {
    turnState.mockResolvedValue({ turn: {} })
    const first = host()
    await waitFor(() => expect(turnState).toHaveBeenCalled())
    expect(screen.queryByText('character.roll_options.succeeded_question')).toBeNull()
    first.unmount()

    turnState.mockClear()
    host('/')
    await new Promise((r) => setTimeout(r, 0))
    expect(turnState).not.toHaveBeenCalled()
  })

  it('non si sovrappone alla domanda nel modale', async () => {
    turnState.mockResolvedValue(pending)
    rollOptions.mockResolvedValue([option({ pay_if_success: true })])
    lastRollOptions.mockResolvedValue({ ...ROLL, total: 12, refundable: ['add'] })
    renderWithProviders(
      <>
        <RefundQuestionHost />
        <RollResultModal result={ROLL} title="Atletica" onClose={() => undefined} afterRoll={{ charId: 1, query: QUERY }} />
      </>,
      { route: '/char/1/skills' },
    )
    await userEvent.click(await screen.findByRole('button', { name: /Aggiungi 1d10\?/ }))
    await waitFor(() => expect(screen.getAllByText('character.roll_options.succeeded_question')).toHaveLength(1))
  })
})

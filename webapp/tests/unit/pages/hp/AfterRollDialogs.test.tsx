import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ConcentrationSaveDialog from '@/pages/hp/ConcentrationSaveDialog'
import DeathSaveResultDialog from '@/pages/hp/DeathSaveResultDialog'
import { renderWithProviders } from '../../utils/renderWithProviders'
import type { ConcentrationSaveResult, DeathSaveRollResult, RollOption } from '@/api/client'

const { rollOptions, lastRollOptions } = vi.hoisted(() => ({ rollOptions: vi.fn(), lastRollOptions: vi.fn() }))
vi.mock('@/api/client', () => ({
  api: { characters: { rollOptions, lastRollOptions } },
  ApiError: class extends Error {},
}))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/hooks/useD20Roll', async (orig) => ({ ...(await orig() as object), useD20Roll: () => async () => [15] }))
vi.mock('@/hooks/useRollNoteLabels', () => ({ useRollNoteLabels: () => (notes: string[]) => notes }))

const again = {
  key: 'again', phase: 'after_roll', label: 'Ritira?', source: 'feature:x', dice: null, bonus: null, mode: null,
  multiplier: null, once_per_turn: false, slot: null, needs: null, requires_input: null, input_options: [],
  auto_fail: false, cost: null, group: null, dice_cost: 0, after: 'reroll',
} as RollOption

beforeEach(() => {
  vi.clearAllMocks()
  rollOptions.mockResolvedValue([again])
})

describe('riga dei privilegi nel TS contro la morte', () => {
  const failed = { die: 5, outcome: 'failure', successes: 0, failures: 1, stable: false, revived: false, current_hp: 0 } as DeathSaveRollResult

  it('un ritiro aggiorna esito e contatori', async () => {
    lastRollOptions.mockResolvedValue({ death: { ...failed, die: 15, outcome: 'success', successes: 1, failures: 0 } })
    renderWithProviders(<DeathSaveResultDialog result={failed} onClose={() => undefined} afterRoll={{ charId: 1 }} />)
    expect(screen.getByText('✓ 0/3 · ✗ 1/3')).toBeInTheDocument()
    await userEvent.click(await screen.findByRole('button', { name: /Ritira\?/ }))
    expect(await screen.findByText('✓ 1/3 · ✗ 0/3')).toBeInTheDocument()
    expect(rollOptions).toHaveBeenCalledWith(1, { roll: 'death_save' })
    expect(screen.getByText('character.death_saves.success')).toBeInTheDocument()
  })

  it('senza afterRoll non chiede nulla', async () => {
    renderWithProviders(<DeathSaveResultDialog result={failed} onClose={() => undefined} />)
    await new Promise((r) => setTimeout(r, 0))
    expect(rollOptions).not.toHaveBeenCalled()
  })
})

describe('riga dei privilegi nel TS di concentrazione', () => {
  const lost = {
    die: 2, bonus: 3, total: 5, is_critical: false, is_fumble: false, description: 'DC 15', dc: 15, success: false,
    lost_concentration: true,
  } as ConcentrationSaveResult

  it('un ritiro riuscito toglie l\'avviso di concentrazione persa', async () => {
    lastRollOptions.mockResolvedValue({ concentration: { ...lost, die: 15, total: 18, success: true, lost_concentration: false } })
    renderWithProviders(<ConcentrationSaveDialog result={lost} onClose={() => undefined} afterRoll={{ charId: 1 }} />)
    expect(screen.getByText('character.spells.conc_lost')).toBeInTheDocument()
    await userEvent.click(await screen.findByRole('button', { name: /Ritira\?/ }))
    expect(await screen.findByText('18')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByText('character.spells.conc_lost')).toBeNull())
    expect(rollOptions).toHaveBeenCalledWith(1, { roll: 'save', ability: 'constitution' })
  })

  it('con un fallimento automatico non offre nulla', async () => {
    renderWithProviders(<ConcentrationSaveDialog result={{ ...lost, auto_fail: true }} onClose={() => undefined} afterRoll={{ charId: 1 }} />)
    await new Promise((r) => setTimeout(r, 0))
    expect(rollOptions).not.toHaveBeenCalled()
  })
})

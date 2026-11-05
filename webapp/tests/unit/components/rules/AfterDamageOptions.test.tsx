import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../../unit/utils/renderWithProviders'
import AfterDamageOptions from '@/components/rules/AfterDamageOptions'
import type { RollDamageResult } from '@/types'

const { rollOptions, lastDamageOptions } = vi.hoisted(() => ({ rollOptions: vi.fn(), lastDamageOptions: vi.fn() }))

vi.mock('@/api/client', () => ({ api: { characters: { rollOptions, lastDamageOptions } } }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('sonner', () => ({ toast: { warning: vi.fn() } }))

const option = (over: object) => ({
  key: 'empowered', phase: 'after_damage', label: 'Potenziato', source: 'feature:x', dice: null, bonus: null, mode: null,
  multiplier: null, once_per_turn: false, slot: null, needs: null, requires_input: null, input_options: [],
  auto_fail: false, group: null, dice_cost: 0, reroll_limit: 2, keep_rolled: false, cost: null, ...over,
})
const result = {
  total: 11, half_damage: 5, main_kind: 'd6', main_rolls: [1, 6], extra_kind: 'd4', extra_rolls: [4], rolls: [1, 6, 4],
} as unknown as RollDamageResult

const dice = () => screen.getAllByRole('button').filter((b) => /^\d+$/.test(b.textContent ?? ''))

afterEach(() => { rollOptions.mockReset(); lastDamageOptions.mockReset() })

describe('AfterDamageOptions', () => {
  it('renders nothing without options of this phase', async () => {
    rollOptions.mockResolvedValue([option({ phase: 'before' })])
    renderWithProviders(<AfterDamageOptions charId={7} spellId={1} result={result} onResult={() => {}} />)
    await waitFor(() => expect(rollOptions).toHaveBeenCalled())
    expect(screen.queryByText('Potenziato')).not.toBeInTheDocument()
  })

  it('rerolls the chosen dice up to the limit and reports the new result', async () => {
    rollOptions.mockResolvedValue([option({})])
    const updated = { ...result, total: 13 }
    lastDamageOptions.mockResolvedValue(updated)
    const onResult = vi.fn()
    renderWithProviders(<AfterDamageOptions charId={7} spellId={1} result={result} onResult={onResult} />)
    await userEvent.click(await screen.findByText('Potenziato'))
    expect(dice()).toHaveLength(3)
    const confirm = screen.getByRole('button', { name: /after_damage_confirm/ })
    expect(confirm).toBeDisabled()

    await userEvent.click(dice()[0])
    await userEvent.click(dice()[1])
    expect(dice()[2]).toBeDisabled()  // limite raggiunto
    await userEvent.click(confirm)
    await waitFor(() => expect(lastDamageOptions).toHaveBeenCalledWith(7, { options: ['empowered'], option_inputs: {}, reroll: [0, 1] }))
    await waitFor(() => expect(onResult).toHaveBeenCalledWith(updated))
  })

  it('keep_rolled offers only the dice showing their maximum', async () => {
    rollOptions.mockResolvedValue([option({ key: 'bombard', label: 'Bombardamento', reroll_limit: 1, keep_rolled: true })])
    renderWithProviders(<AfterDamageOptions charId={7} spellId={1} result={result} onResult={() => {}} />)
    await userEvent.click(await screen.findByText('Bombardamento'))
    expect(dice().map((d) => d.textContent)).toEqual(['6', '4'])  // 1d6 mostra 1: escluso
  })
})

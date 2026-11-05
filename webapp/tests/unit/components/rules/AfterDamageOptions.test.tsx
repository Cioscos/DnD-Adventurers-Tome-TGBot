import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../../unit/utils/renderWithProviders'
import AfterDamageOptions from '@/components/rules/AfterDamageOptions'

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
// Due d6 e un d4, come li passa la scheda dell'incantesimo.
const dice = [{ value: 1, index: 0, sides: 6 }, { value: 6, index: 1, sides: 6 }, { value: 4, index: 2, sides: 4 }]
const spell = { roll: 'spell_damage', spell_id: 1 } as const
const result = { total: 11 }
const buttons = () => screen.getAllByRole('button').filter((b) => /^\d+$/.test(b.textContent ?? ''))

afterEach(() => { rollOptions.mockReset(); lastDamageOptions.mockReset() })

describe('AfterDamageOptions', () => {
  it('renders nothing without options of this phase', async () => {
    rollOptions.mockResolvedValue([option({ phase: 'before' })])
    renderWithProviders(<AfterDamageOptions charId={7} query={spell} dice={dice} onResult={() => {}} />)
    await waitFor(() => expect(rollOptions).toHaveBeenCalled())
    expect(screen.queryByText('Potenziato')).not.toBeInTheDocument()
  })

  it('rerolls the chosen dice up to the limit and reports the new result', async () => {
    rollOptions.mockResolvedValue([option({})])
    const updated = { ...result, total: 13 }
    lastDamageOptions.mockResolvedValue(updated)
    const onResult = vi.fn()
    renderWithProviders(<AfterDamageOptions charId={7} query={spell} dice={dice} onResult={onResult} />)
    await userEvent.click(await screen.findByText('Potenziato'))
    expect(buttons()).toHaveLength(3)
    const confirm = screen.getByRole('button', { name: /after_damage_confirm/ })
    expect(confirm).toBeDisabled()

    await userEvent.click(buttons()[0])
    await userEvent.click(buttons()[1])
    expect(buttons()[2]).toBeDisabled()  // limite raggiunto
    await userEvent.click(confirm)
    await waitFor(() => expect(lastDamageOptions).toHaveBeenCalledWith(7, { options: ['empowered'], option_inputs: {}, reroll: [0, 1] }))
    await waitFor(() => expect(onResult).toHaveBeenCalledWith(updated))
  })

  it('keep_rolled offers only the dice showing their maximum', async () => {
    rollOptions.mockResolvedValue([option({ key: 'bombard', label: 'Bombardamento', reroll_limit: 1, keep_rolled: true })])
    renderWithProviders(<AfterDamageOptions charId={7} query={spell} dice={dice} onResult={() => {}} />)
    await userEvent.click(await screen.findByText('Bombardamento'))
    expect(buttons().map((d) => d.textContent)).toEqual(['6', '4'])  // 1d6 mostra 1: escluso
  })

  it('asks the weapon damage options and rerolls a die of the weapon roll', async () => {
    rollOptions.mockResolvedValue([option({ key: 'inspiration:reroll_damage', reroll_limit: 1 })])
    lastDamageOptions.mockResolvedValue({ damage_total: 9 })
    const onResult = vi.fn()
    renderWithProviders(<AfterDamageOptions charId={7} query={{ roll: 'weapon_damage' }}
      dice={[{ value: 2, index: 0, sides: 8 }, { value: 5, index: 1, sides: 8 }]} onResult={onResult} />)
    await userEvent.click(await screen.findByText('Potenziato'))
    expect(rollOptions).toHaveBeenCalledWith(7, { roll: 'weapon_damage' })
    await userEvent.click(buttons()[0])
    await userEvent.click(screen.getByRole('button', { name: /after_damage_confirm/ }))
    await waitFor(() => expect(lastDamageOptions).toHaveBeenCalledWith(7, { options: ['inspiration:reroll_damage'], option_inputs: {}, reroll: [0] }))
    await waitFor(() => expect(onResult).toHaveBeenCalledWith({ damage_total: 9 }))
  })
})

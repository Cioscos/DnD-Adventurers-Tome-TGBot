import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../utils/renderWithProviders'
import userEvent from '@testing-library/user-event'
import Dice from '@/pages/Dice'

const { getChar, history, initiative } = vi.hoisted(() => ({ getChar: vi.fn(), history: vi.fn(), initiative: vi.fn() }))

vi.mock('@/api/client', () => ({ api: { characters: { get: getChar }, dice: { history, initiative } } }))
vi.mock('@/hooks/useD20Roll', () => ({
  useD20Roll: () => async () => undefined,
  d20Arg: (mode: string) => (mode === 'normal' ? undefined : { dice: undefined, mode }),
}))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '7' }) }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }), isInsideTelegram: () => false }))
vi.mock('@/store/characterStore', () => ({ useCharacterStore: (sel: (s: { locale: string }) => unknown) => sel({ locale: 'it' }) }))
vi.mock('@/dice/useRollAndPersist', () => ({ useRollAndPersist: () => ({ roll: vi.fn(), isPending: false }) }))
vi.mock('@/dice/preload', () => ({ schedulePreloadDiceScene: () => {} }))
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/ConfirmSheet', () => ({ default: () => null }))

afterEach(() => { getChar.mockReset(); history.mockReset(); initiative.mockReset() })

describe('Dice', () => {
  it('initiative shows the sheet bonus and the server result with the reason of its mode', async () => {
    getChar.mockResolvedValue({ id: 7, name: 'Aragorn', ability_scores: [{ name: 'dexterity', modifier: 3 }], initiative_bonus: 1 })
    history.mockResolvedValue([])
    initiative.mockResolvedValue({
      die: 4, dice: [4, 18], mode: 'disadvantage', bonus: 1, total: 5,
      is_critical: false, is_fumble: false, notes: ['condition:poisoned'],
    })
    renderWithProviders(<Dice />)
    const button = await screen.findByRole('button', { name: 'character.dice.initiative' })
    expect(await screen.findByText(/d20 \+1/)).toBeInTheDocument()
    await userEvent.click(button)
    await vi.waitFor(() => expect(initiative).toHaveBeenCalledWith(7, undefined, 'character.dice.initiative'))
    expect(await screen.findByTestId('roll-notes')).toHaveTextContent('character.conditions.poisoned')
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('stays usable and says the history is unavailable when its fetch fails', async () => {
    getChar.mockResolvedValue({ id: 7, name: 'Aragorn', ability_scores: [] })
    history.mockRejectedValue(new TypeError('Failed to fetch'))
    renderWithProviders(<Dice />)
    expect(await screen.findByText('common.offline_unavailable')).toBeInTheDocument()
  })

  it('shows no offline state when the history is simply empty', async () => {
    getChar.mockResolvedValue({ id: 7, name: 'Aragorn', ability_scores: [] })
    history.mockResolvedValue([])
    renderWithProviders(<Dice />)
    await vi.waitFor(() => expect(history).toHaveBeenCalled())
    expect(screen.queryByText('common.offline_unavailable')).not.toBeInTheDocument()
  })
})

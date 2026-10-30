import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../utils/renderWithProviders'
import Dice from '@/pages/Dice'

const { getChar, history } = vi.hoisted(() => ({ getChar: vi.fn(), history: vi.fn() }))

vi.mock('@/api/client', () => ({ api: { characters: { get: getChar }, dice: { history } } }))
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

afterEach(() => { getChar.mockReset(); history.mockReset() })

describe('Dice', () => {
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

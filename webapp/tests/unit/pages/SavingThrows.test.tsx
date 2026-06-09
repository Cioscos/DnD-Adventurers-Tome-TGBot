import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import SavingThrows from '@/pages/SavingThrows'

const { getChar, updateSavingThrows, rollSavingThrow, toastError, playAndCollect } = vi.hoisted(() => ({
  getChar: vi.fn(),
  updateSavingThrows: vi.fn(),
  rollSavingThrow: vi.fn(),
  toastError: vi.fn(),
  playAndCollect: vi.fn(),
}))

// Compat contract:
//  - api.characters.updateSavingThrows(id, Record<string,boolean>) → PATCH /saving_throws {saving_throws}
//  - api.characters.rollSavingThrow(id, ability, die?, withInspiration?) → POST .../roll → RollResult
vi.mock('@/api/client', () => {
  class ApiError extends Error {
    status: number
    constructor(status: number) {
      super('api')
      this.status = status
    }
  }
  return {
    api: { characters: { get: getChar, updateSavingThrows, rollSavingThrow } },
    ApiError,
  }
})

vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '5' }) }
})

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'drag', 'layout'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return { m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }) }
})

vi.mock('@/auth/telegram', () => ({ haptic: { light: () => {}, success: () => {}, error: () => {} } }))
vi.mock('@/styles/motion', () => ({ stagger: new Proxy({}, { get: () => 0 }) }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: toastError, info: vi.fn(), success: vi.fn() }) }))
vi.mock('@/hooks/useReducedMotion', () => ({ useReducedMotion: () => true }))
vi.mock('@/dice/useDiceAnimation', () => ({ useDiceAnimation: () => ({ playAndCollect }) }))
// animate3d=false → roll path never enters the 3D branch ⇒ die stays undefined (server rolls).
vi.mock('@/store/diceSettings', () => ({
  useDiceSettings: (sel: (s: { animate3d: boolean }) => unknown) => sel({ animate3d: false }),
}))

vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/Surface', async () => {
  const React = await import('react')
  return {
    default: (p: { onClick?: () => void; children?: unknown }) =>
      React.createElement('div', { onClick: p.onClick }, p.children),
  }
})
vi.mock('@/components/ui/Reveal', async () => {
  const React = await import('react')
  const C = (p: { children?: unknown }) => React.createElement('div', null, p.children)
  return { default: { Stagger: C, Item: C } }
})
vi.mock('@/components/ui/StatPill', async () => {
  const React = await import('react')
  return { default: (p: { value: unknown }) => React.createElement('span', { 'data-testid': 'pb' }, String(p.value)) }
})
vi.mock('@/components/ui/DiceIcon', async () => ({ default: () => null }))
vi.mock('@/components/homebrew/HomebrewBreakdownRow', async () => ({ default: () => null }))
vi.mock('@/components/skeletons/SavingThrowsSkeleton', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'saves-skeleton' }) }
})
vi.mock('@/components/RollResultModal', async () => {
  const React = await import('react')
  return {
    default: (p: {
      title: string
      result: { total: number }
      inspirationAvailable?: boolean
      wasRerolled?: boolean
      onInspirationReroll?: () => void
      onClose: () => void
    }) =>
      React.createElement(
        'div',
        { 'data-testid': 'roll-modal' },
        React.createElement('span', { 'data-testid': 'roll-total' }, String(p.result.total)),
        p.inspirationAvailable && !p.wasRerolled && p.onInspirationReroll
          ? React.createElement('button', { onClick: p.onInspirationReroll }, 'reroll')
          : null,
        React.createElement('button', { onClick: p.onClose }, 'close'),
      ),
  }
})

// Guerriero-like L1 (PB +2): STR & CON saves proficient; STR mod +2 (rest absent → 0).
const baseChar = {
  id: 5,
  total_level: 1,
  heroic_inspiration: false,
  saving_throws: { strength: true, constitution: true },
  ability_scores: [{ name: 'strength', modifier: 2 }],
  saves_homebrew_modifiers: {},
}
const rollResult = { die: 10, bonus: 2, total: 12, is_critical: false, is_fumble: false, description: 'strength' }

afterEach(() => {
  getChar.mockReset()
  updateSavingThrows.mockReset()
  rollSavingThrow.mockReset()
  toastError.mockReset()
  playAndCollect.mockReset()
})

describe('SavingThrows page', () => {
  it('shows the skeleton while the character query is pending', () => {
    getChar.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<SavingThrows />)
    expect(screen.getByTestId('saves-skeleton')).toBeInTheDocument()
  })

  it('renders PB and a proficient save total (mod + PB)', async () => {
    getChar.mockResolvedValue(baseChar)
    renderWithProviders(<SavingThrows />)
    expect(await screen.findByTestId('pb')).toHaveTextContent('+2')
    // STR: mod +2 + PB +2 = +4 (only proficient ability with a non-zero mod).
    expect(screen.getByText('+4')).toBeInTheDocument()
  })

  it('toggling proficiency merges the flipped value into the existing map', async () => {
    getChar.mockResolvedValue(baseChar)
    updateSavingThrows.mockResolvedValue(baseChar)
    renderWithProviders(<SavingThrows />)
    await screen.findByTestId('pb')
    // First "Proficiency" toggle == STR (ABILITIES[0]); stopPropagation keeps it off the roll path.
    await userEvent.click(screen.getAllByLabelText('Proficiency')[0])
    await waitFor(() =>
      expect(updateSavingThrows).toHaveBeenCalledWith(5, { strength: false, constitution: true }),
    )
  })

  it('rolling a save calls rollSavingThrow with no die (server rolls) and opens the modal', async () => {
    getChar.mockResolvedValue(baseChar)
    rollSavingThrow.mockResolvedValue(rollResult)
    renderWithProviders(<SavingThrows />)
    await screen.findByTestId('pb')
    await userEvent.click(screen.getByText('character.stats.strength'))
    await waitFor(() => expect(rollSavingThrow).toHaveBeenCalledWith(5, 'strength', undefined))
    expect(await screen.findByTestId('roll-total')).toHaveTextContent('12')
  })

  it('inspiration reroll re-rolls with the with_inspiration flag', async () => {
    getChar.mockResolvedValue({ ...baseChar, heroic_inspiration: true })
    rollSavingThrow.mockResolvedValueOnce(rollResult).mockResolvedValueOnce({ ...rollResult, total: 19 })
    renderWithProviders(<SavingThrows />)
    await screen.findByTestId('pb')
    await userEvent.click(screen.getByText('character.stats.strength'))
    await userEvent.click(await screen.findByText('reroll'))
    await waitFor(() =>
      expect(rollSavingThrow).toHaveBeenLastCalledWith(5, 'strength', undefined, true),
    )
  })

  it('shows an error toast when an inspiration reroll 409s', async () => {
    const { ApiError } = await import('@/api/client')
    getChar.mockResolvedValue({ ...baseChar, heroic_inspiration: true })
    rollSavingThrow
      .mockResolvedValueOnce(rollResult)
      .mockRejectedValueOnce(new (ApiError as new (s: number) => Error)(409))
    renderWithProviders(<SavingThrows />)
    await screen.findByTestId('pb')
    await userEvent.click(screen.getByText('character.stats.strength'))
    await userEvent.click(await screen.findByText('reroll'))
    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith('character.inspiration.unavailable_error'),
    )
  })
})

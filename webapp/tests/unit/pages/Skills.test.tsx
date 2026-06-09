import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Skills from '@/pages/Skills'

const { getChar, updateSkills, rollSkill, toastError, playAndCollect } = vi.hoisted(() => ({
  getChar: vi.fn(),
  updateSkills: vi.fn(),
  rollSkill: vi.fn(),
  toastError: vi.fn(),
  playAndCollect: vi.fn(),
}))

// Compat contract:
//  - api.characters.updateSkills(id, Record<string,unknown>) → PATCH /skills {skills}
//  - api.characters.rollSkill(id, skillName, die?, withInspiration?) → POST .../roll → RollResult
vi.mock('@/api/client', () => {
  class ApiError extends Error {
    status: number
    constructor(status: number) {
      super('api')
      this.status = status
    }
  }
  return { api: { characters: { get: getChar, updateSkills, rollSkill } }, ApiError }
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

vi.mock('@/auth/telegram', () => ({ haptic: { light: () => {}, medium: () => {}, success: () => {}, error: () => {} } }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: toastError, info: vi.fn(), success: vi.fn() }) }))
vi.mock('@/hooks/useReducedMotion', () => ({ useReducedMotion: () => true }))
vi.mock('@/dice/useDiceAnimation', () => ({ useDiceAnimation: () => ({ playAndCollect }) }))
vi.mock('@/store/diceSettings', () => ({
  useDiceSettings: (sel: (s: { animate3d: boolean }) => unknown) => sel({ animate3d: false }),
}))
// Surface the tap (onClick) and long-press (onContextMenu) handlers as plain DOM events;
// the timing behaviour of the real hook is covered by useLongPress.test.ts.
vi.mock('@/hooks/useLongPress', () => ({
  useLongPress: (opts: { onClick?: () => void; onLongPress?: () => void }) => ({
    onClick: opts.onClick,
    onContextMenu: (e: { preventDefault?: () => void }) => {
      e.preventDefault?.()
      opts.onLongPress?.()
    },
  }),
}))

const passthrough = vi.hoisted(() => async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/Layout', passthrough)
vi.mock('@/components/ui/Surface', passthrough)
vi.mock('@/components/ui/SectionDivider', passthrough)
vi.mock('@/components/ScrollArea', passthrough)
vi.mock('@/components/ui/StatPill', async () => {
  const React = await import('react')
  return { default: (p: { value: unknown }) => React.createElement('span', null, String(p.value)) }
})
vi.mock('@/components/homebrew/HomebrewBreakdownRow', async () => ({ default: () => null }))
vi.mock('@/components/skeletons/SkillsSkeleton', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'skills-skeleton' }) }
})
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return {
    default: (p: { open: boolean; children?: unknown }) =>
      p.open ? React.createElement('div', { 'data-testid': 'picker' }, p.children) : null,
  }
})
vi.mock('@/components/RollResultModal', async () => {
  const React = await import('react')
  return {
    default: (p: {
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

// L5 → PB +3. athletics expert (STR +3), acrobatics proficient (DEX +2), stealth none.
const baseChar = {
  id: 5,
  total_level: 5,
  heroic_inspiration: false,
  skills: { athletics: 'expert', acrobatics: true },
  ability_scores: [
    { name: 'strength', modifier: 3 },
    { name: 'dexterity', modifier: 2 },
    { name: 'wisdom', modifier: 1 },
  ],
  skills_homebrew_modifiers: {},
}
const rollResult = { die: 14, bonus: 9, total: 23, is_critical: false, is_fumble: false, description: 'athletics' }

afterEach(() => {
  getChar.mockReset()
  updateSkills.mockReset()
  rollSkill.mockReset()
  toastError.mockReset()
  playAndCollect.mockReset()
})

describe('Skills page', () => {
  it('shows the skeleton while the character query is pending', () => {
    getChar.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<Skills />)
    expect(screen.getByTestId('skills-skeleton')).toBeInTheDocument()
  })

  it('doubles the proficiency bonus for an EXPERT skill (mod + 2×PB)', async () => {
    getChar.mockResolvedValue(baseChar)
    renderWithProviders(<Skills />)
    // athletics expert: +3 mod + 2×(+3 PB) = +9.
    expect(await screen.findByText('+9')).toBeInTheDocument()
    // passive perception = 10 + (WIS +1, no prof) = 11.
    expect(screen.getByText('11')).toBeInTheDocument()
  })

  it('tapping a skill cycles its proficiency level and PATCHes it', async () => {
    getChar.mockResolvedValue(baseChar)
    updateSkills.mockResolvedValue(baseChar)
    renderWithProviders(<Skills />)
    // athletics is currently 'expert' → next in the cycle is false.
    await userEvent.click(await screen.findByText('character.skills.athletics'))
    await waitFor(() => expect(updateSkills).toHaveBeenCalledWith(5, { athletics: false }))
  })

  it('long-press opens the picker and the chosen level is PATCHed', async () => {
    getChar.mockResolvedValue(baseChar)
    updateSkills.mockResolvedValue(baseChar)
    renderWithProviders(<Skills />)
    fireEvent.contextMenu(await screen.findByText('character.skills.stealth'))
    expect(await screen.findByTestId('picker')).toBeInTheDocument()
    await userEvent.click(screen.getByText('character.skills.proficient'))
    await waitFor(() => expect(updateSkills).toHaveBeenCalledWith(5, { stealth: true }))
  })

  it('rolling a skill calls rollSkill with no die and opens the modal', async () => {
    getChar.mockResolvedValue(baseChar)
    rollSkill.mockResolvedValue(rollResult)
    renderWithProviders(<Skills />)
    await screen.findByText('+9')
    // First roll button == athletics (STR group renders first).
    await userEvent.click(screen.getAllByLabelText('character.skills.roll')[0])
    await waitFor(() => expect(rollSkill).toHaveBeenCalledWith(5, 'athletics', undefined))
    expect(await screen.findByTestId('roll-total')).toHaveTextContent('23')
  })

  it('shows an error toast when an inspiration reroll 409s', async () => {
    const { ApiError } = await import('@/api/client')
    getChar.mockResolvedValue({ ...baseChar, heroic_inspiration: true })
    rollSkill
      .mockResolvedValueOnce(rollResult)
      .mockRejectedValueOnce(new (ApiError as new (s: number) => Error)(409))
    renderWithProviders(<Skills />)
    await screen.findByText('+9')
    await userEvent.click(screen.getAllByLabelText('character.skills.roll')[0])
    await userEvent.click(await screen.findByText('reroll'))
    await waitFor(() => expect(rollSkill).toHaveBeenLastCalledWith(5, 'athletics', undefined, true))
    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith('character.inspiration.unavailable_error'),
    )
  })
})

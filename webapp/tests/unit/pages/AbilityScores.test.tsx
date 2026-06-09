import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import AbilityScores from '@/pages/AbilityScores'

const { getChar, updateAbilityScore, toastSuccess } = vi.hoisted(() => ({
  getChar: vi.fn(),
  updateAbilityScore: vi.fn(),
  toastSuccess: vi.fn(),
}))

// Compat contract: AbilityScores → api.characters.updateAbilityScore(id, ability, value)
// → PATCH /characters/{id}/ability_scores/{ability} {value} → CharacterFull.
vi.mock('@/api/client', () => ({
  api: { characters: { get: getChar, updateAbilityScore } },
}))

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
  return {
    m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }),
    AnimatePresence: (p: { children?: unknown }) => p.children,
  }
})

vi.mock('sonner', () => ({ toast: { success: toastSuccess, error: vi.fn() } }))
vi.mock('@/auth/telegram', () => ({ haptic: { success: () => {}, error: () => {} } }))
vi.mock('@/styles/motion', () => ({
  ease: new Proxy({}, { get: () => ({}) }),
  stagger: new Proxy({}, { get: () => 0 }),
}))

const passthrough = vi.hoisted(() => async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/Layout', passthrough)
vi.mock('@/components/ui/Reveal', async () => {
  const React = await import('react')
  const C = (p: { children?: unknown }) => React.createElement('div', null, p.children)
  return { default: { Stagger: C, Item: C } }
})
vi.mock('@/components/character/AbilityScoreDetail', async () => ({ default: () => null }))
vi.mock('@/components/skeletons/AbilityScoresSkeleton', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'stats-skeleton' }) }
})

// Card: surfaces the score value + an edit affordance so we can open the modal.
vi.mock('@/components/character/AbilityScoreCard', async () => {
  const React = await import('react')
  return {
    default: (p: { score: { name: string; value: number }; onEdit: () => void }) =>
      React.createElement(
        'button',
        { 'data-testid': `edit-${p.score.name}`, onClick: p.onEdit },
        String(p.score.value),
      ),
  }
})

// Edit modal: when open, exposes three save paths so handleSave's guards are testable.
vi.mock('@/components/character/AbilityScoreEditModal', async () => {
  const React = await import('react')
  return {
    default: (p: { open: boolean; currentValue: number; onSave: (v: number) => void }) =>
      p.open
        ? React.createElement(
            'div',
            null,
            React.createElement('button', { onClick: () => p.onSave(18) }, 'save18'),
            React.createElement('button', { onClick: () => p.onSave(0) }, 'save-invalid'),
            React.createElement('button', { onClick: () => p.onSave(p.currentValue) }, 'save-same'),
          )
        : null,
  }
})

const baseChar = {
  id: 5,
  hit_points: 10,
  ability_scores: [
    { name: 'strength', value: 14, modifier: 2 },
    { name: 'constitution', value: 12, modifier: 1 },
  ],
}

afterEach(() => {
  getChar.mockReset()
  updateAbilityScore.mockReset()
  toastSuccess.mockReset()
})

describe('AbilityScores page', () => {
  it('shows the skeleton while the character query is pending', () => {
    getChar.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<AbilityScores />)
    expect(screen.getByTestId('stats-skeleton')).toBeInTheDocument()
  })

  it('renders each ability score value (read contract)', async () => {
    getChar.mockResolvedValue(baseChar)
    renderWithProviders(<AbilityScores />)
    expect(await screen.findByTestId('edit-strength')).toHaveTextContent('14')
    expect(screen.getByTestId('edit-constitution')).toHaveTextContent('12')
  })

  it('saves a valid new value via PATCH /ability_scores/{name} {value}', async () => {
    getChar.mockResolvedValue(baseChar)
    updateAbilityScore.mockResolvedValue({ ...baseChar })
    renderWithProviders(<AbilityScores />)
    await userEvent.click(await screen.findByTestId('edit-strength'))
    await userEvent.click(screen.getByText('save18'))
    await waitFor(() =>
      expect(updateAbilityScore).toHaveBeenCalledWith(5, 'strength', 18),
    )
  })

  it('does not PATCH when the value is out of the 1..30 range', async () => {
    getChar.mockResolvedValue(baseChar)
    renderWithProviders(<AbilityScores />)
    await userEvent.click(await screen.findByTestId('edit-strength'))
    await userEvent.click(screen.getByText('save-invalid'))
    expect(updateAbilityScore).not.toHaveBeenCalled()
  })

  it('does not PATCH when the value is unchanged', async () => {
    getChar.mockResolvedValue(baseChar)
    renderWithProviders(<AbilityScores />)
    await userEvent.click(await screen.findByTestId('edit-strength'))
    await userEvent.click(screen.getByText('save-same')) // currentValue === 14
    expect(updateAbilityScore).not.toHaveBeenCalled()
  })

  it('fires an HP-recalc toast when CONSTITUTION changes the max HP', async () => {
    getChar.mockResolvedValue(baseChar)
    // CON edit → server recomputes hit_points (10 → 18).
    updateAbilityScore.mockResolvedValue({ ...baseChar, hit_points: 18 })
    renderWithProviders(<AbilityScores />)
    await userEvent.click(await screen.findByTestId('edit-constitution'))
    await userEvent.click(screen.getByText('save18'))
    // toast.success(t(key, {...})) → with the key-returning i18n mock this is a single arg.
    await waitFor(() =>
      expect(toastSuccess).toHaveBeenCalledWith('character.stats.hp_recalc_toast'),
    )
  })
})

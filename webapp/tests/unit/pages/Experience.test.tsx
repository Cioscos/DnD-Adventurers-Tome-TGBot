import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Experience from '@/pages/Experience'

const { getChar, updateXPSpy, toastSuccess, confettiSpy } = vi.hoisted(() => ({
  getChar: vi.fn(),
  updateXPSpy: vi.fn(),
  toastSuccess: vi.fn(),
  confettiSpy: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: { characters: { get: getChar, updateXP: updateXPSpy } },
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
  return { m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }) }
})

vi.mock('sonner', () => ({ toast: { success: toastSuccess, error: vi.fn() } }))
vi.mock('@/lib/celebrate', () => ({ fireLevelUpConfetti: confettiSpy }))
vi.mock('@/auth/telegram', () => ({ haptic: { success: () => {}, error: () => {} } }))
vi.mock('@/hooks/useReducedMotion', () => ({ useReducedMotion: () => true }))
vi.mock('@/styles/motion', () => ({
  spring: new Proxy({}, { get: () => ({}) }),
  ease: new Proxy({}, { get: () => ({}) }),
}))

const passthrough = vi.hoisted(() => async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
const nullModule = vi.hoisted(() => async () => ({ default: () => null }))
vi.mock('@/components/Layout', passthrough)
vi.mock('@/components/ui/Surface', passthrough)
vi.mock('@/components/ui/StatPill', nullModule)
vi.mock('@/components/character/ClassTabs', nullModule)
vi.mock('@/components/character/ProgressionPreview', nullModule)
vi.mock('@/pages/multiclass/LevelUpBanner', nullModule)
vi.mock('@/pages/multiclass/LevelUpModal', nullModule)
vi.mock('@/components/ui/Ornament', () => ({ CornerFlourish: () => null }))
vi.mock('@/components/ui/AnimatedNumber', async () => {
  const React = await import('react')
  return { default: (p: { value: number }) => React.createElement('span', null, String(p.value)) }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return {
    default: (p: { onClick?: () => void; disabled?: boolean; children?: unknown }) =>
      React.createElement('button', { onClick: p.onClick, disabled: p.disabled }, p.children),
  }
})
vi.mock('@/components/ui/Input', async () => {
  const React = await import('react')
  return {
    default: (p: { value: string; placeholder?: string; type?: string; onChange: (v: string) => void }) =>
      React.createElement('input', {
        value: p.value,
        placeholder: p.placeholder,
        type: p.type,
        onChange: (e: { target: { value: string } }) => p.onChange(e.target.value),
      }),
  }
})
vi.mock('@/components/skeletons/ExperienceSkeleton', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'xp-skeleton' }) }
})

// CharacterFull-shaped fixture: 900 XP = level 3 (XP_THRESHOLDS[2]=900), next at 2700.
// No classes → ClassTabs/progression block stays unmounted, single-class note hidden.
const baseChar = { id: 5, experience_points: 900, abilities: [], classes: [] }

afterEach(() => {
  getChar.mockReset()
  updateXPSpy.mockReset()
  toastSuccess.mockReset()
  confettiSpy.mockReset()
})

describe('Experience page', () => {
  it('shows the skeleton while the character query is pending', () => {
    getChar.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<Experience />)
    expect(screen.getByTestId('xp-skeleton')).toBeInTheDocument()
  })

  it('derives level 3 from 900 XP and renders the XP value (read contract)', async () => {
    getChar.mockResolvedValue(baseChar)
    renderWithProviders(<Experience />)
    expect(await screen.findByText('3')).toBeInTheDocument() // level from levelFromXp(900)
    expect(screen.getByText('900')).toBeInTheDocument()      // experience_points
  })

  it('add mode applies a positive delta via PATCH /xp {add}', async () => {
    getChar.mockResolvedValue(baseChar)
    updateXPSpy.mockResolvedValue({ ...baseChar, experience_points: 950 })
    renderWithProviders(<Experience />)
    await screen.findByText('3')

    fireEvent.change(screen.getByPlaceholderText('character.xp.label'), { target: { value: '50' } })
    await userEvent.click(screen.getByRole('button', { name: 'common.applica' }))
    await waitFor(() =>
      expect(updateXPSpy).toHaveBeenCalledWith(5, { add: 50, set: undefined }),
    )
  })

  it('set mode overwrites the absolute value via PATCH /xp {set}', async () => {
    getChar.mockResolvedValue(baseChar)
    updateXPSpy.mockResolvedValue({ ...baseChar, experience_points: 1000 })
    renderWithProviders(<Experience />)
    await screen.findByText('3')

    await userEvent.click(screen.getByRole('button', { name: /character\.currency\.mode_set/ }))
    fireEvent.change(screen.getByPlaceholderText('character.xp.label'), { target: { value: '1000' } })
    await userEvent.click(screen.getByRole('button', { name: 'common.applica' }))
    await waitFor(() =>
      expect(updateXPSpy).toHaveBeenCalledWith(5, { add: undefined, set: 1000 }),
    )
  })

  it('the level-up CTA jumps XP to the next threshold (set = XP_THRESHOLDS[level])', async () => {
    getChar.mockResolvedValue(baseChar)
    updateXPSpy.mockResolvedValue(baseChar) // unchanged → no level-up toast
    renderWithProviders(<Experience />)
    await screen.findByText('3')

    await userEvent.click(screen.getByRole('button', { name: 'character.xp.level_up_cta' }))
    await waitFor(() =>
      expect(updateXPSpy).toHaveBeenCalledWith(5, { add: undefined, set: 2700 }),
    )
  })

  it('fires a level-up toast when the new XP crosses a level boundary', async () => {
    getChar.mockResolvedValue(baseChar)
    // 2700 XP = level 4 (> old level 3) → level-up branch.
    updateXPSpy.mockResolvedValue({ ...baseChar, experience_points: 2700 })
    renderWithProviders(<Experience />)
    await screen.findByText('3')

    await userEvent.click(screen.getByRole('button', { name: 'character.xp.level_up_cta' }))
    await waitFor(() =>
      expect(toastSuccess).toHaveBeenCalledWith('character.xp.level_up_toast', expect.anything()),
    )
  })

  it('fires an HP-gained toast when the response reports hp_gained', async () => {
    getChar.mockResolvedValue(baseChar)
    updateXPSpy.mockResolvedValue({ ...baseChar, experience_points: 950, hp_gained: 8 })
    renderWithProviders(<Experience />)
    await screen.findByText('3')

    fireEvent.change(screen.getByPlaceholderText('character.xp.label'), { target: { value: '50' } })
    await userEvent.click(screen.getByRole('button', { name: 'common.applica' }))
    await waitFor(() =>
      expect(toastSuccess).toHaveBeenCalledWith('character.xp.hp_gained_toast', expect.anything()),
    )
  })
})

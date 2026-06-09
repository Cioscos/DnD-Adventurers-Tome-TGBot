import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import LevelUpModal from '@/pages/multiclass/LevelUpModal'

const { distributeSpy, toastSuccess, toastInfo, confettiSpy } = vi.hoisted(() => ({
  distributeSpy: vi.fn(),
  toastSuccess: vi.fn(),
  toastInfo: vi.fn(),
  confettiSpy: vi.fn(),
}))

vi.mock('@/api/client', () => ({ api: { classes: { distribute: distributeSpy } } }))

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'layout'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return { m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }) }
})

vi.mock('sonner', () => ({ toast: { success: toastSuccess, info: toastInfo } }))
vi.mock('@/lib/celebrate', () => ({ fireLevelUpConfetti: confettiSpy }))
vi.mock('@/hooks/useReducedMotion', () => ({ useReducedMotion: () => false }))
vi.mock('@/store/overlayStore', () => ({ useRegisterOverlay: () => {} }))
vi.mock('@/auth/telegram', () => ({ haptic: { success: () => {}, error: () => {}, medium: () => {} } }))

const passthrough = vi.hoisted(() => async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/Surface', passthrough)
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return {
    default: (p: { onClick?: () => void; disabled?: boolean; children?: unknown }) =>
      React.createElement('button', { onClick: p.onClick, disabled: p.disabled }, p.children),
  }
})
vi.mock('@/components/ui/Ornament', async () => {
  const React = await import('react')
  const Noop = () => React.createElement('span')
  return { CornerFlourishes: Noop, FlourishDivider: Noop }
})

// class_name is the canonical English lowercase key; the real classProgression
// bridge maps it to the Italian progression table — kept un-mocked on purpose.
const char = (overrides: Record<string, unknown> = {}) => ({
  id: 5,
  classes: [
    { id: 21, class_name: 'wizard', level: 3 },
    { id: 22, class_name: 'fighter', level: 2 },
  ],
  ...overrides,
})

afterEach(() => {
  distributeSpy.mockReset()
  toastSuccess.mockReset()
  toastInfo.mockReset()
  confettiSpy.mockReset()
})

describe('LevelUpModal', () => {
  it('renders a selector button per class with its current level', () => {
    renderWithProviders(<LevelUpModal char={char()} xpLevel={6} onClose={vi.fn()} />)
    expect(screen.getByText('wizard')).toBeInTheDocument()
    expect(screen.getByText('fighter')).toBeInTheDocument()
  })

  it('confirming distributes a +1 to the default (first) class, others unchanged', async () => {
    distributeSpy.mockResolvedValue({ id: 5, hp_gained: 0, classes: [] })
    const onClose = vi.fn()
    renderWithProviders(<LevelUpModal char={char()} xpLevel={6} onClose={onClose} />)
    await userEvent.click(screen.getByRole('button', { name: 'character.multiclass.level_up.confirm' }))
    await waitFor(() =>
      expect(distributeSpy).toHaveBeenCalledWith(5, [
        { class_id: 21, level: 4 },
        { class_id: 22, level: 2 },
      ]),
    )
    expect(toastSuccess).toHaveBeenCalled()       // level-up celebration
    expect(confettiSpy).toHaveBeenCalled()         // !reducedMotion → confetti
    expect(onClose).toHaveBeenCalled()
  })

  it('selecting another class redirects the +1 to it', async () => {
    distributeSpy.mockResolvedValue({ id: 5, hp_gained: 0, classes: [] })
    renderWithProviders(<LevelUpModal char={char()} xpLevel={6} onClose={vi.fn()} />)
    await userEvent.click(screen.getByText('fighter'))
    await userEvent.click(screen.getByRole('button', { name: 'character.multiclass.level_up.confirm' }))
    await waitFor(() =>
      expect(distributeSpy).toHaveBeenCalledWith(5, [
        { class_id: 21, level: 3 },
        { class_id: 22, level: 3 },
      ]),
    )
  })

  it('fires the extra hp_gained toast when the response reports gained HP', async () => {
    distributeSpy.mockResolvedValue({ id: 5, hp_gained: 6, classes: [] })
    renderWithProviders(<LevelUpModal char={char()} xpLevel={6} onClose={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'character.multiclass.level_up.confirm' }))
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledTimes(2)) // level-up + hp_gained
  })

  it('disables confirm and never distributes when the selected class is at level 20', async () => {
    // first (default-selected) class at the 5e cap
    renderWithProviders(
      <LevelUpModal
        char={char({ classes: [{ id: 21, class_name: 'wizard', level: 20 }, { id: 22, class_name: 'fighter', level: 2 }] })}
        xpLevel={22}
        onClose={vi.fn()}
      />,
    )
    const confirm = screen.getByRole('button', { name: 'character.multiclass.level_up.confirm' })
    expect(confirm).toBeDisabled()
    await userEvent.click(confirm)
    expect(distributeSpy).not.toHaveBeenCalled()
  })
})

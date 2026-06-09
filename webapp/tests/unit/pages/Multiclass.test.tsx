import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Multiclass from '@/pages/Multiclass'

// Spies hoisted so the vi.mock factories can close over them.
const { getChar, removeSpy } = vi.hoisted(() => ({
  getChar: vi.fn(),
  removeSpy: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: {
    characters: { get: getChar },
    classes: { remove: removeSpy },
  },
}))

vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '7' }) }
})

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

// framer-motion: strip motion props, keep DOM-valid ones (onClick/aria-label survive).
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

vi.mock('@/auth/telegram', () => ({
  haptic: { light: () => {}, medium: () => {}, success: () => {}, error: () => {} },
}))

const passthrough = vi.hoisted(() => async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/Layout', passthrough)
vi.mock('@/components/ui/Surface', passthrough)

vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return {
    default: (p: { onClick?: () => void; disabled?: boolean; children?: unknown }) =>
      React.createElement('button', { onClick: p.onClick, disabled: p.disabled }, p.children),
  }
})
vi.mock('@/components/ui/StatPill', async () => {
  const React = await import('react')
  return { default: (p: { value?: unknown }) => React.createElement('span', null, p.value) }
})
vi.mock('@/components/ui/EmptyState', async () => {
  const React = await import('react')
  return { default: (p: { title?: unknown }) => React.createElement('div', { 'data-testid': 'empty' }, p.title) }
})
vi.mock('@/components/ui/Ornament', async () => {
  const React = await import('react')
  const Noop = () => React.createElement('span')
  return { FlourishDivider: Noop, CornerFlourishes: Noop }
})
vi.mock('@/components/skeletons/MulticlassSkeleton', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'multiclass-skeleton' }) }
})
// LevelUpBanner exposes onOpen; the modals just signal that they mounted.
vi.mock('@/pages/multiclass/LevelUpBanner', async () => {
  const React = await import('react')
  return {
    default: (p: { onOpen?: () => void }) =>
      React.createElement('button', { onClick: p.onOpen }, 'levelup-banner'),
  }
})
vi.mock('@/pages/multiclass/LevelUpModal', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'levelup-modal' }) }
})
vi.mock('@/pages/multiclass/EditClassesModal', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'edit-classes-modal' }) }
})
// ConfirmSheet renders the confirm button only while open (so onConfirm is reachable).
vi.mock('@/components/ui/ConfirmSheet', async () => {
  const React = await import('react')
  return {
    default: (p: { open?: boolean; onConfirm?: () => void; confirmLabel?: string }) =>
      p.open ? React.createElement('button', { onClick: p.onConfirm }, p.confirmLabel) : null,
  }
})

// CharacterFull-shaped fixture (only the fields Multiclass reads).
const wizard = { id: 11, class_name: 'wizard', level: 2, subclass: 'Evocation', hit_die: 6, spellcasting_ability: 'intelligence' }
// xp 900 → levelFromXp = 3 (the real xpThresholds lib is used, not mocked)
const char = (overrides = {}) => ({ id: 7, experience_points: 900, classes: [wizard], ...overrides })

afterEach(() => {
  getChar.mockReset()
  removeSpy.mockReset()
})

describe('Multiclass page', () => {
  it('shows the skeleton while the character query is pending', () => {
    getChar.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<Multiclass />)
    expect(screen.getByTestId('multiclass-skeleton')).toBeInTheDocument()
  })

  it('renders the total level from levelFromXp and the class card', async () => {
    getChar.mockResolvedValue(char())
    renderWithProviders(<Multiclass />)
    // total level = levelFromXp(900) = 3
    expect(await screen.findByText('3')).toBeInTheDocument()
    expect(screen.getByText('wizard')).toBeInTheDocument()
    expect(screen.getByText('(Evocation)')).toBeInTheDocument()
    expect(screen.getByText('d6')).toBeInTheDocument()
    // class level badge (read-only) = 2
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('offers the level-up banner when xp level exceeds distributed class levels', async () => {
    getChar.mockResolvedValue(char()) // classes sum 2 < target 3
    renderWithProviders(<Multiclass />)
    expect(await screen.findByText('levelup-banner')).toBeInTheDocument()
  })

  it('hides the level-up banner when classes already match the xp level', async () => {
    getChar.mockResolvedValue(char({ classes: [{ ...wizard, level: 3 }] })) // sum 3 == target 3
    renderWithProviders(<Multiclass />)
    await screen.findByText('wizard')
    expect(screen.queryByText('levelup-banner')).not.toBeInTheDocument()
  })

  it('opens the manage-classes modal', async () => {
    getChar.mockResolvedValue(char())
    renderWithProviders(<Multiclass />)
    await userEvent.click(await screen.findByText('character.multiclass.manage_classes'))
    expect(screen.getByTestId('edit-classes-modal')).toBeInTheDocument()
  })

  it('shows the empty state when there are no classes', async () => {
    getChar.mockResolvedValue(char({ classes: [] }))
    renderWithProviders(<Multiclass />)
    expect(await screen.findByTestId('empty')).toHaveTextContent('character.multiclass.empty_state_title')
  })

  it('removing a class confirms then DELETEs it', async () => {
    getChar.mockResolvedValue(char())
    removeSpy.mockResolvedValue(char())
    renderWithProviders(<Multiclass />)
    await userEvent.click(await screen.findByLabelText('Remove'))
    // ConfirmSheet now open → confirm button (confirmLabel = common.delete).
    await userEvent.click(screen.getByRole('button', { name: 'common.delete' }))
    await waitFor(() => expect(removeSpy).toHaveBeenCalledWith(7, 11))
  })
})

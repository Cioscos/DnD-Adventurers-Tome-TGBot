import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import SpellSlots from '@/pages/SpellSlots'

// Spies hoisted so the vi.mock factories can close over them.
const { getChar, updateSpy, addSpy, removeSpy, resetSpy } = vi.hoisted(() => ({
  getChar: vi.fn(),
  updateSpy: vi.fn(),
  addSpy: vi.fn(),
  removeSpy: vi.fn(),
  resetSpy: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: {
    characters: { get: getChar },
    spellSlots: { update: updateSpy, add: addSpy, remove: removeSpy, resetAll: resetSpy },
  },
}))

vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '9' }), useNavigate: () => vi.fn() }
})

// Identity translator → labels resolve to their i18n KEY (locale-free, interpolation ignored).
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

// framer-motion: strip motion props, keep DOM-valid ones (onClick/onPointerDown survive).
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

vi.mock('@/auth/telegram', () => ({
  haptic: { light: () => {}, medium: () => {}, success: () => {}, error: () => {} },
}))
vi.mock('@/styles/motion', () => ({ stagger: { list: 0.1 } }))

const passthrough = vi.hoisted(() => async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/Layout', passthrough)
vi.mock('@/components/ui/Surface', passthrough)

// Reveal is a compound { Stagger, Item }; both just render their children.
vi.mock('@/components/ui/Reveal', async () => {
  const React = await import('react')
  const Pass = (p: { children?: unknown }) => React.createElement('div', null, p.children)
  return { default: { Stagger: Pass, Item: Pass } }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return {
    default: (p: { onClick?: () => void; disabled?: boolean; children?: unknown }) =>
      React.createElement('button', { onClick: p.onClick, disabled: p.disabled }, p.children),
  }
})
vi.mock('@/components/ui/EmptyState', async () => {
  const React = await import('react')
  return { default: (p: { title?: unknown }) => React.createElement('div', { 'data-testid': 'empty' }, p.title) }
})
// ConfirmSheet renders a confirm button only while open (so onConfirm is reachable).
vi.mock('@/components/ui/ConfirmSheet', async () => {
  const React = await import('react')
  return {
    default: (p: { open?: boolean; onConfirm?: () => void; confirmLabel?: string }) =>
      p.open
        ? React.createElement('button', { onClick: p.onConfirm }, p.confirmLabel)
        : null,
  }
})
vi.mock('@/components/character/AutoModeBanner', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'auto-banner' }) }
})
vi.mock('@/components/skeletons/SpellSlotsSkeleton', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'spellslots-skeleton' }) }
})

// SpellSlotRead-shaped fixture (the exact BE serializer shape the FE reads).
const slot = { id: 100, level: 1, total: 3, used: 1, available: 2, is_pact: false }
const manualChar = { id: 9, settings: { spell_slots_mode: 'manual' }, spell_slots: [slot] }
const autoChar = { id: 9, settings: { spell_slots_mode: 'auto' }, spell_slots: [slot] }

afterEach(() => {
  getChar.mockReset()
  updateSpy.mockReset()
  addSpy.mockReset()
  removeSpy.mockReset()
  resetSpy.mockReset()
})

describe('SpellSlots page', () => {
  it('shows the skeleton while the character query is pending', () => {
    getChar.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<SpellSlots />)
    expect(screen.getByTestId('spellslots-skeleton')).toBeInTheDocument()
  })

  it('renders available/total and the roman level from the SpellSlotRead shape', async () => {
    getChar.mockResolvedValue(manualChar)
    renderWithProviders(<SpellSlots />)
    // available 2 / total 3, level 1 → roman "I"
    expect(await screen.findByText('2/3')).toBeInTheDocument()
    expect(screen.getByText('I')).toBeInTheDocument()
  })

  it('casting an available gem PATCHes used+1 (clamped to total)', async () => {
    getChar.mockResolvedValue(manualChar)
    updateSpy.mockResolvedValue(slot)
    renderWithProviders(<SpellSlots />)
    await screen.findByText('2/3')

    // total=3 gems; index 0 is used (filled), 1 & 2 are available.
    const gems = screen.getAllByLabelText('character.slots.gem_aria')
    await userEvent.click(gems[1])
    await waitFor(() =>
      expect(updateSpy).toHaveBeenCalledWith(9, 100, { used: 2 }),
    )
  })

  it('clicking a used gem PATCHes used-1 (clamped to 0)', async () => {
    getChar.mockResolvedValue(manualChar)
    updateSpy.mockResolvedValue(slot)
    renderWithProviders(<SpellSlots />)
    await screen.findByText('2/3')

    const gems = screen.getAllByLabelText('character.slots.gem_aria')
    await userEvent.click(gems[0]) // the one filled gem
    await waitFor(() =>
      expect(updateSpy).toHaveBeenCalledWith(9, 100, { used: 0 }),
    )
  })

  it('editing the total commits a PATCH with {total} on blur', async () => {
    getChar.mockResolvedValue(manualChar)
    updateSpy.mockResolvedValue(slot)
    renderWithProviders(<SpellSlots />)
    await screen.findByText('2/3')

    const totalInput = screen.getByRole('spinbutton')
    fireEvent.change(totalInput, { target: { value: '5' } })
    fireEvent.blur(totalInput)
    await waitFor(() =>
      expect(updateSpy).toHaveBeenCalledWith(9, 100, { total: 5 }),
    )
  })

  it('adding a missing level POSTs a new slot (level, total=1)', async () => {
    getChar.mockResolvedValue(manualChar)
    addSpy.mockResolvedValue(slot)
    renderWithProviders(<SpellSlots />)
    await screen.findByText('2/3')

    // Only level 1 exists → first missing level is 2.
    const addButtons = screen.getAllByRole('button', { name: /character\.slots\.level/ })
    await userEvent.click(addButtons[0])
    await waitFor(() => expect(addSpy).toHaveBeenCalledWith(9, 2, 1))
  })

  it('removing a slot DELETEs it', async () => {
    getChar.mockResolvedValue(manualChar)
    removeSpy.mockResolvedValue(undefined)
    renderWithProviders(<SpellSlots />)
    await screen.findByText('2/3')

    await userEvent.click(screen.getByLabelText('Remove'))
    await waitFor(() => expect(removeSpy).toHaveBeenCalledWith(9, 100))
  })

  it('reset-all confirms then POSTs the reset (returns the full character)', async () => {
    getChar.mockResolvedValue(manualChar)
    resetSpy.mockResolvedValue(manualChar)
    renderWithProviders(<SpellSlots />)
    await screen.findByText('2/3')

    await userEvent.click(screen.getByRole('button', { name: 'character.slots.reset_all' }))
    // ConfirmSheet now open → confirm button (confirmLabel = common.confirm).
    await userEvent.click(screen.getByRole('button', { name: 'common.confirm' }))
    await waitFor(() => expect(resetSpy).toHaveBeenCalledWith(9))
  })

  it('auto mode hides the manual affordances and shows the auto banner', async () => {
    getChar.mockResolvedValue(autoChar)
    renderWithProviders(<SpellSlots />)
    await screen.findByText('2/3')

    expect(screen.getByTestId('auto-banner')).toBeInTheDocument()
    expect(screen.queryByLabelText('Remove')).not.toBeInTheDocument()
    expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument()
    // No "add level" buttons in auto mode.
    expect(screen.queryAllByRole('button', { name: /character\.slots\.level/ })).toHaveLength(0)
  })
})

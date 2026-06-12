import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Spells from '@/pages/Spells'

const {
  getChar, updateChar, addSpy, updateSpy, removeSpy, useSpy, concSpy, slotUpdateSpy, slotAddSpy, toastInfo,
} = vi.hoisted(() => ({
  getChar: vi.fn(),
  updateChar: vi.fn(),
  addSpy: vi.fn(),
  updateSpy: vi.fn(),
  removeSpy: vi.fn(),
  useSpy: vi.fn(),
  concSpy: vi.fn(),
  slotUpdateSpy: vi.fn(),
  slotAddSpy: vi.fn(),
  toastInfo: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: {
    characters: { get: getChar, update: updateChar },
    spells: { add: addSpy, update: updateSpy, remove: removeSpy, use: useSpy, updateConcentration: concSpy },
    spellSlots: { update: slotUpdateSpy, add: slotAddSpy },
  },
}))

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})

// react-router-dom: pin the id; keep the real useSearchParams (MemoryRouter provides it).
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '9' }) }
})

vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'layout'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return {
    m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }),
    AnimatePresence: (p: { children?: unknown }) => p.children,
    useDragControls: () => ({ start: () => {} }),
  }
})

vi.mock('sonner', () => ({ toast: { info: toastInfo, error: vi.fn(), success: vi.fn() } }))
vi.mock('@/auth/telegram', () => ({
  haptic: { light: () => {}, medium: () => {}, success: () => {}, error: () => {} },
}))

const passthrough = vi.hoisted(() => async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/Layout', passthrough)
vi.mock('@/components/ui/Surface', passthrough)
vi.mock('@/components/ScrollArea', passthrough)
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
vi.mock('@/components/ui/FilterChip', async () => {
  const React = await import('react')
  return { default: (p: { label?: unknown }) => React.createElement('span', null, p.label) }
})
vi.mock('@/components/ui/FilterRow', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/skeletons/SpellsSkeleton', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'spells-skeleton' }) }
})

// SpellFilter → just exposes the "add" affordance.
vi.mock('@/pages/spells/SpellFilter', async () => {
  const React = await import('react')
  return { default: (p: { onAddClick?: () => void }) => React.createElement('button', { onClick: p.onAddClick }, 'add-spell') }
})
// SpellItem → one labelled button per callback the page wires.
vi.mock('@/pages/spells/SpellItem', async () => {
  const React = await import('react')
  return {
    default: (p: { spell: { name: string }; onUse?: () => void; onConcentrationToggle?: () => void; onEdit?: () => void; onRemove?: () => void }) =>
      React.createElement('div', null, [
        React.createElement('span', { key: 'n' }, p.spell.name),
        React.createElement('button', { key: 'u', onClick: p.onUse }, `use-${p.spell.name}`),
        React.createElement('button', { key: 'c', onClick: p.onConcentrationToggle }, `conc-${p.spell.name}`),
        React.createElement('button', { key: 'r', onClick: p.onRemove }, `remove-${p.spell.name}`),
      ]),
  }
})
// SpellForm → submits a fixed SpellFormData so we can assert the add contract.
vi.mock('@/pages/spells/SpellForm', async () => {
  const React = await import('react')
  const FORM_DATA = {
    name: 'Magic Missile', level: '1', description: '', casting_time: '', range_area: '',
    components: '', duration: '', is_concentration: false, is_ritual: false,
    damage_dice: '3d4+3', damage_type: 'force',
  }
  return { default: (p: { onSubmit?: (d: unknown) => void }) => React.createElement('button', { onClick: () => p.onSubmit?.(FORM_DATA) }, 'submit-spell') }
})
// CastSpellModal → a cast button per available slot + a create-slot button.
vi.mock('@/pages/spells/CastSpellModal', async () => {
  const React = await import('react')
  return {
    default: (p: { spell: { level: number }; availableSlots: { id: number; level: number }[]; onCast?: (l: number) => void; onCreateSlot?: (l: number) => void }) =>
      React.createElement('div', { 'data-testid': 'cast-modal' }, [
        ...p.availableSlots.map((s) =>
          React.createElement('button', { key: `cast-${s.id}`, onClick: () => p.onCast?.(s.level) }, `cast-slot-${s.level}`)),
        React.createElement('button', { key: 'create', onClick: () => p.onCreateSlot?.(p.spell.level) }, `create-slot-${p.spell.level}`),
      ]),
  }
})
// SpellDamageSheet → marker carrying the deferred slot level (no API call yet).
vi.mock('@/pages/spells/SpellDamageSheet', async () => {
  const React = await import('react')
  return {
    default: (p: { spell: { name: string } | null; slotLevel: number | null }) =>
      p.spell ? React.createElement('div', { 'data-testid': 'damage-sheet', 'data-slot': String(p.slotLevel) }, p.spell.name) : null,
  }
})

// CharacterFull-shaped fixture (only the fields Spells reads).
const manualChar = () => ({
  id: 9,
  settings: { spell_slots_mode: 'manual' },
  concentrating_spell_id: null,
  spells: [
    { id: 101, name: 'Fire Bolt', level: 0, is_concentration: false, is_ritual: false, damage_dice: '1d10' },
    { id: 102, name: 'Bless', level: 1, is_concentration: true, is_ritual: false },
    { id: 103, name: 'Fireball', level: 3, is_concentration: false, is_ritual: false, damage_dice: '8d6' },
    { id: 104, name: 'Guidance', level: 0, is_concentration: true, is_ritual: false },
  ],
  spell_slots: [
    { id: 201, level: 1, total: 3, used: 1, available: 2, is_pact: false },
    { id: 203, level: 3, total: 2, used: 0, available: 2, is_pact: false },
  ],
})

afterEach(() => {
  for (const s of [getChar, updateChar, addSpy, updateSpy, removeSpy, useSpy, concSpy, slotUpdateSpy, slotAddSpy, toastInfo]) s.mockReset()
})

describe('Spells page', () => {
  it('shows the skeleton while the character query is pending', () => {
    getChar.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<Spells />)
    expect(screen.getByTestId('spells-skeleton')).toBeInTheDocument()
  })

  it('renders the spells and one slot gem per total across the leveled groups', async () => {
    getChar.mockResolvedValue(manualChar())
    renderWithProviders(<Spells />)
    expect(await screen.findByText('Bless')).toBeInTheDocument()
    expect(screen.getByText('Fireball')).toBeInTheDocument()
    // slot gems: 3 (level 1) + 2 (level 3) = 5
    expect(screen.getAllByLabelText('character.slots.gem_aria')).toHaveLength(5)
  })

  it('casting a leveled non-damage concentration spell consumes a slot and sets concentration', async () => {
    getChar.mockResolvedValue(manualChar())
    useSpy.mockResolvedValue(manualChar())
    concSpy.mockResolvedValue(manualChar())
    renderWithProviders(<Spells />)
    await userEvent.click(await screen.findByText('use-Bless'))
    await userEvent.click(await screen.findByText('cast-slot-1'))
    await waitFor(() => expect(useSpy).toHaveBeenCalledWith(9, 102, 1))
    await waitFor(() => expect(concSpy).toHaveBeenCalledWith(9, 102)) // Bless is_concentration
  })

  it('casting a leveled damage spell defers to the damage sheet (no slot consumed yet)', async () => {
    getChar.mockResolvedValue(manualChar())
    renderWithProviders(<Spells />)
    await userEvent.click(await screen.findByText('use-Fireball'))
    await userEvent.click(await screen.findByText('cast-slot-3'))
    const sheet = await screen.findByTestId('damage-sheet')
    expect(sheet).toHaveTextContent('Fireball')
    expect(sheet).toHaveAttribute('data-slot', '3')
    expect(useSpy).not.toHaveBeenCalled()
  })

  it('using a damage cantrip opens the damage sheet at slot level 0', async () => {
    getChar.mockResolvedValue(manualChar())
    renderWithProviders(<Spells />)
    await userEvent.click(await screen.findByText('use-Fire Bolt'))
    const sheet = await screen.findByTestId('damage-sheet')
    expect(sheet).toHaveTextContent('Fire Bolt')
    expect(sheet).toHaveAttribute('data-slot', '0')
  })

  it('using a concentration cantrip toggles concentration without a slot', async () => {
    getChar.mockResolvedValue(manualChar())
    concSpy.mockResolvedValue(manualChar())
    renderWithProviders(<Spells />)
    await userEvent.click(await screen.findByText('use-Guidance'))
    await waitFor(() => expect(concSpy).toHaveBeenCalledWith(9, 104))
  })

  // gems[0..2] = level-1 slot (used 1): index 0 lit, indices 1-2 available.
  // Fresh render per assertion — the success handler refetches and re-renders.
  it('clicking a used slot gem refunds it (used-1, clamped)', async () => {
    getChar.mockResolvedValue(manualChar())
    slotUpdateSpy.mockResolvedValue({ id: 201 })
    renderWithProviders(<Spells />)
    await screen.findByText('Bless')
    const gems = screen.getAllByLabelText('character.slots.gem_aria')
    await userEvent.click(gems[0]) // lit → refund → used-1 = 0
    await waitFor(() => expect(slotUpdateSpy).toHaveBeenCalledWith(9, 201, { used: 0 }))
  })

  it('clicking an available slot gem casts from it (used+1, clamped)', async () => {
    getChar.mockResolvedValue(manualChar())
    slotUpdateSpy.mockResolvedValue({ id: 201 })
    renderWithProviders(<Spells />)
    await screen.findByText('Bless')
    const gems = screen.getAllByLabelText('character.slots.gem_aria')
    await userEvent.click(gems[1]) // available → cast → used+1 = 2
    await waitFor(() => expect(slotUpdateSpy).toHaveBeenCalledWith(9, 201, { used: 2 }))
  })

  it('toggling concentration from a spell row PATCHes the concentrating spell', async () => {
    getChar.mockResolvedValue(manualChar())
    concSpy.mockResolvedValue(manualChar())
    renderWithProviders(<Spells />)
    await userEvent.click(await screen.findByText('conc-Bless'))
    await waitFor(() => expect(concSpy).toHaveBeenCalledWith(9, 102))
  })

  it('removing a spell asks for confirmation, then DELETEs it', async () => {
    getChar.mockResolvedValue(manualChar())
    removeSpy.mockResolvedValue(undefined)
    renderWithProviders(<Spells />)
    await userEvent.click(await screen.findByText('remove-Bless'))
    // Nessuna DELETE finché l'utente non conferma (audit #9).
    expect(removeSpy).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'character.spells.forget' }))
    await waitFor(() => expect(removeSpy).toHaveBeenCalledWith(9, 102))
  })

  it('adding a spell POSTs the trimmed SpellCreate contract', async () => {
    getChar.mockResolvedValue(manualChar())
    addSpy.mockResolvedValue({ id: 999 })
    renderWithProviders(<Spells />)
    await userEvent.click(await screen.findByText('add-spell'))
    await userEvent.click(await screen.findByText('submit-spell'))
    await waitFor(() =>
      expect(addSpy).toHaveBeenCalledWith(9, {
        name: 'Magic Missile',
        level: 1,
        description: undefined,
        casting_time: undefined,
        range_area: undefined,
        components: undefined,
        duration: undefined,
        is_concentration: false,
        is_ritual: false,
        damage_dice: '3d4+3',
        damage_type: 'force',
        is_pinned: false,
      }),
    )
  })

  it('creating a slot from the cast modal in auto mode switches to manual then adds the slot', async () => {
    getChar.mockResolvedValue({
      id: 9,
      settings: { spell_slots_mode: 'auto' },
      concentrating_spell_id: null,
      spells: [{ id: 110, name: 'Web', level: 2, is_concentration: true, is_ritual: false }],
      spell_slots: [],
    })
    updateChar.mockResolvedValue({ id: 9 })
    slotAddSpy.mockResolvedValue({ id: 301 })
    renderWithProviders(<Spells />)
    await userEvent.click(await screen.findByText('use-Web'))
    await userEvent.click(await screen.findByText('create-slot-2'))
    await waitFor(() =>
      expect(updateChar).toHaveBeenCalledWith(9, { settings: { spell_slots_mode: 'manual' } }),
    )
    await waitFor(() => expect(slotAddSpy).toHaveBeenCalledWith(9, 2, 1))
    expect(toastInfo).toHaveBeenCalled() // notice that auto → manual happened
  })
})

import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Abilities from '@/pages/Abilities'

const { getChar, listResources, patchResource, addSpy, updateSpy, removeSpy } = vi.hoisted(() => ({
  getChar: vi.fn(),
  listResources: vi.fn(),
  patchResource: vi.fn(),
  addSpy: vi.fn(),
  updateSpy: vi.fn(),
  removeSpy: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: {
    characters: { get: getChar },
    homebrew: { listResources, patchResource },
    abilities: { add: addSpy, update: updateSpy, remove: removeSpy },
  },
}))

vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '3' }) }
})

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
  return {
    m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }),
    AnimatePresence: (p: { children?: unknown }) => p.children,
  }
})

vi.mock('@/auth/telegram', () => ({
  haptic: { light: () => {}, medium: () => {}, success: () => {}, error: () => {} },
}))
vi.mock('@/styles/motion', () => ({ spring: { press: {} } }))

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
// Input → bare input exposing onChange(value) and an accessible name from label.
vi.mock('@/components/ui/Input', async () => {
  const React = await import('react')
  return {
    default: (p: { label?: string; value?: string; onChange?: (v: string) => void }) =>
      React.createElement('input', {
        'aria-label': p.label,
        value: p.value ?? '',
        onChange: (e: { target: { value: string } }) => p.onChange?.(e.target.value),
      }),
  }
})
// Sheet → renders children only while open.
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return {
    default: (p: { open?: boolean; children?: unknown }) =>
      p.open ? React.createElement('div', null, p.children) : null,
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
// FilterChip/FilterRow → non-button spans so they don't pollute button/pressed queries.
vi.mock('@/components/ui/FilterChip', async () => {
  const React = await import('react')
  return { default: (p: { label?: unknown }) => React.createElement('span', null, p.label) }
})
vi.mock('@/components/ui/FilterRow', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
// CustomResourceCounter → three explicit buttons for the homebrew resource flow.
vi.mock('@/components/homebrew/CustomResourceCounter', async () => {
  const React = await import('react')
  return {
    default: (p: { onDecrement?: () => void; onIncrement?: () => void; onRestore?: () => void }) =>
      React.createElement('div', null, [
        React.createElement('button', { key: 'd', onClick: p.onDecrement }, 'res-dec'),
        React.createElement('button', { key: 'i', onClick: p.onIncrement }, 'res-inc'),
        React.createElement('button', { key: 'r', onClick: p.onRestore }, 'res-restore'),
      ]),
  }
})
vi.mock('@/components/skeletons/AbilitiesSkeleton', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'abilities-skeleton' }) }
})

// Ability-shaped fixtures (the exact BE AbilityRead shape the FE consumes).
const classFeature = {
  id: 1, name: 'Action Surge', description: 'old', max_uses: 1, uses: 1,
  is_passive: false, is_active: true, restoration_type: 'short_rest',
  source_class_id: 10, is_class_feature: true,
}
const lucky = {
  id: 2, name: 'Lucky', description: 'luck', max_uses: 3, uses: 1,
  is_passive: false, is_active: true, restoration_type: 'manual',
  is_class_feature: false,
}
const char = (abilities: unknown[] = []) => ({
  id: 3,
  classes: [{ id: 10, class_name: 'fighter', level: 5 }],
  abilities,
})

beforeEach(() => {
  listResources.mockResolvedValue([])
})
afterEach(() => {
  getChar.mockReset()
  listResources.mockReset()
  patchResource.mockReset()
  addSpy.mockReset()
  updateSpy.mockReset()
  removeSpy.mockReset()
})

describe('Abilities page', () => {
  it('shows the skeleton while the character query is pending', () => {
    getChar.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<Abilities />)
    expect(screen.getByTestId('abilities-skeleton')).toBeInTheDocument()
  })

  it('groups abilities into class-features and custom sections', async () => {
    getChar.mockResolvedValue(char([classFeature, lucky]))
    renderWithProviders(<Abilities />)
    expect(await screen.findByText('character.abilities.class_features_section')).toBeInTheDocument()
    expect(screen.getByText('character.abilities.custom_section')).toBeInTheDocument()
  })

  it('add wizard: applies the detected restoration and posts the AbilityCreate contract', async () => {
    getChar.mockResolvedValue(char([]))
    addSpy.mockResolvedValue({ id: 9 })
    renderWithProviders(<Abilities />)

    await userEvent.click(await screen.findByRole('button', { name: 'character.abilities.add' }))
    // step 1 — name (smart-default sets restoration to short_rest for "Action Surge")
    await userEvent.type(screen.getByLabelText('character.abilities.name_label'), 'Action Surge')
    await userEvent.click(screen.getByRole('button', { name: 'common.next' }))
    // step 2 — max uses, leave the auto restoration untouched
    await userEvent.type(screen.getByLabelText('character.abilities.max_uses_label'), '3')
    await userEvent.click(screen.getByRole('button', { name: 'common.add' }))

    await waitFor(() =>
      expect(addSpy).toHaveBeenCalledWith(3, {
        name: 'Action Surge',
        description: undefined,
        max_uses: 3,
        uses: 3,
        is_passive: false,
        is_active: true,
        restoration_type: 'short_rest',
      }),
    )
  })

  it('pips: lit pip (already-used) restores a use', async () => {
    getChar.mockResolvedValue(char([lucky]))   // max 3, uses 1 → 2 lit (used) + 1 unlit
    updateSpy.mockResolvedValue({ id: 2 })
    renderWithProviders(<Abilities />)

    await userEvent.click(await screen.findByRole('button', { name: /Lucky/ }))   // expand
    // lit pips = aria-pressed true (already-used), unlit = false (still available)
    const lit = screen.getAllByRole('button', { pressed: true })
    expect(lit).toHaveLength(2)
    expect(screen.getAllByRole('button', { pressed: false })).toHaveLength(1)

    await userEvent.click(lit[0])             // restore → uses current+1 = 2
    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith(3, 2, { uses: 2 }))
  })

  it('pips: unlit pip (still available) spends a use', async () => {
    getChar.mockResolvedValue(char([lucky]))
    updateSpy.mockResolvedValue({ id: 2 })
    renderWithProviders(<Abilities />)

    await userEvent.click(await screen.findByRole('button', { name: /Lucky/ }))   // expand
    const unlit = screen.getAllByRole('button', { pressed: false })
    await userEvent.click(unlit[0])           // spend → uses current-1 = 0
    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith(3, 2, { uses: 0 }))
  })

  it('deletes a custom ability', async () => {
    getChar.mockResolvedValue(char([lucky]))
    removeSpy.mockResolvedValue(undefined)
    renderWithProviders(<Abilities />)
    await userEvent.click(await screen.findByRole('button', { name: /Lucky/ }))   // expand
    await userEvent.click(screen.getByRole('button', { name: 'common.delete' }))
    await waitFor(() => expect(removeSpy).toHaveBeenCalledWith(3, 2))
  })

  it('class feature is locked to a description-only PATCH', async () => {
    getChar.mockResolvedValue(char([classFeature]))
    updateSpy.mockResolvedValue({ id: 1 })
    renderWithProviders(<Abilities />)

    await userEvent.click(await screen.findByRole('button', { name: /Action Surge/ }))   // expand
    await userEvent.click(screen.getByRole('button', { name: 'character.abilities.edit_description' }))
    // description-only sheet now open
    const field = screen.getByLabelText('character.abilities.description_label')
    await userEvent.clear(field)
    await userEvent.type(field, 'new desc')
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith(3, 1, { description: 'new desc' }))
  })

  // Each interaction gets a fresh render: the success handler optimistically
  // rewrites the cached `current`, so chaining clicks would drift the baseline.
  it('homebrew resource: increment clamps to max', async () => {
    getChar.mockResolvedValue(char([]))
    listResources.mockResolvedValue([{ id: 99, name: 'Rage', current: 2, max: 5 }])
    patchResource.mockResolvedValue({ id: 99, name: 'Rage', current: 3, max: 5 })
    renderWithProviders(<Abilities />)
    await userEvent.click(await screen.findByText('res-inc'))
    await waitFor(() => expect(patchResource).toHaveBeenCalledWith(3, 99, 3)) // min(5, 2+1)
  })

  it('homebrew resource: decrement floors at 0', async () => {
    getChar.mockResolvedValue(char([]))
    listResources.mockResolvedValue([{ id: 99, name: 'Rage', current: 2, max: 5 }])
    patchResource.mockResolvedValue({ id: 99, name: 'Rage', current: 1, max: 5 })
    renderWithProviders(<Abilities />)
    await userEvent.click(await screen.findByText('res-dec'))
    await waitFor(() => expect(patchResource).toHaveBeenCalledWith(3, 99, 1)) // max(0, 2-1)
  })

  it('homebrew resource: restore jumps to max', async () => {
    getChar.mockResolvedValue(char([]))
    listResources.mockResolvedValue([{ id: 99, name: 'Rage', current: 2, max: 5 }])
    patchResource.mockResolvedValue({ id: 99, name: 'Rage', current: 5, max: 5 })
    renderWithProviders(<Abilities />)
    await userEvent.click(await screen.findByText('res-restore'))
    await waitFor(() => expect(patchResource).toHaveBeenCalledWith(3, 99, 5)) // restore to max
  })
})

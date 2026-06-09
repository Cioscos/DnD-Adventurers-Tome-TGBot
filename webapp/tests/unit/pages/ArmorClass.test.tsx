import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import ArmorClass from '@/pages/ArmorClass'

const { getChar, updateACSpy, resetOverrideSpy, setUnarmoredSpy } = vi.hoisted(() => ({
  getChar: vi.fn(),
  updateACSpy: vi.fn(),
  resetOverrideSpy: vi.fn(),
  setUnarmoredSpy: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: {
    characters: {
      get: getChar,
      updateAC: updateACSpy,
      resetACOverride: resetOverrideSpy,
      setUnarmoredDefense: setUnarmoredSpy,
    },
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

vi.mock('@/auth/telegram', () => ({ haptic: { success: () => {}, error: () => {} } }))
vi.mock('@/styles/motion', () => ({ spring: new Proxy({}, { get: () => ({}) }) }))
vi.mock('@/hooks/useReducedMotion', () => ({ useReducedMotion: () => true }))

// Hoisted so the (also hoisted) vi.mock factories below can use it.
const passthrough = vi.hoisted(() => async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/Layout', passthrough)
vi.mock('@/components/ui/Surface', passthrough)
vi.mock('@/components/homebrew/HomebrewBreakdownRow', passthrough)
vi.mock('@/components/ui/Ornament', async () => {
  const React = await import('react')
  return { ShieldEmblem: () => React.createElement('div', { 'data-testid': 'shield-emblem' }) }
})
vi.mock('@/components/skeletons/ArmorClassSkeleton', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'ac-skeleton' }) }
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
    default: (p: { value: string; placeholder?: string; disabled?: boolean; onChange: (v: string) => void }) =>
      React.createElement('input', {
        value: p.value,
        placeholder: p.placeholder,
        disabled: p.disabled,
        onChange: (e: { target: { value: string } }) => p.onChange(e.target.value),
      }),
  }
})

// CharacterFull fixture (only the fields ArmorClass.tsx reads). Distinct AC parts
// so each <Input> placeholder is unique and addressable.
const acChar = {
  id: 7,
  ac: 17,
  ac_breakdown: { homebrew: 0 },
  base_armor_class: 14,
  shield_armor_class: 2,
  magic_armor: 1,
  base_armor_class_override: false,
  shield_armor_class_override: false,
  unarmored_defense_ability: null as 'wisdom' | 'constitution' | null,
  ability_scores: [
    { name: 'dexterity', value: 14 },
    { name: 'wisdom', value: 16 },
    { name: 'constitution', value: 12 },
  ],
  items: [],
}

afterEach(() => {
  getChar.mockReset()
  updateACSpy.mockReset()
  resetOverrideSpy.mockReset()
  setUnarmoredSpy.mockReset()
})

describe('ArmorClass page', () => {
  it('shows the skeleton while the character query is pending', () => {
    getChar.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<ArmorClass />)
    expect(screen.getByTestId('ac-skeleton')).toBeInTheDocument()
  })

  it('renders total AC = ac + homebrew and the base+shield+magic breakdown (read contract)', async () => {
    getChar.mockResolvedValue(acChar)
    renderWithProviders(<ArmorClass />)
    expect(await screen.findByText('17')).toBeInTheDocument() // ac(17) + homebrew(0)
    expect(screen.getByText('14 + 2 + 1')).toBeInTheDocument()
  })

  it('save is disabled until a field is dirty, then PATCHes only the filled fields', async () => {
    getChar.mockResolvedValue(acChar)
    updateACSpy.mockResolvedValue(acChar)
    renderWithProviders(<ArmorClass />)
    await screen.findByText('17')

    const save = screen.getByRole('button', { name: 'common.save' })
    expect(save).toBeDisabled()

    fireEvent.change(screen.getByPlaceholderText('14'), { target: { value: '15' } }) // base only
    expect(screen.getByRole('button', { name: 'common.save' })).toBeEnabled()
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    // empty shield/magic serialize to undefined (untouched server-side)
    await waitFor(() => expect(updateACSpy).toHaveBeenCalledWith(7, { base: 15, shield: undefined, magic: undefined }))
  })

  it('previews the new total live while dirty', async () => {
    getChar.mockResolvedValue(acChar)
    renderWithProviders(<ArmorClass />)
    await screen.findByText('17')
    fireEvent.change(screen.getByPlaceholderText('14'), { target: { value: '20' } }) // base 20 + shield 2 + magic 1 = 23
    expect(await screen.findByText('23')).toBeInTheDocument()
  })

  it('reset-to-auto fires resetACOverride when an override is active', async () => {
    getChar.mockResolvedValue({ ...acChar, base_armor_class_override: true })
    resetOverrideSpy.mockResolvedValue(acChar)
    renderWithProviders(<ArmorClass />)
    await screen.findByText('17')

    await userEvent.click(screen.getByRole('button', { name: 'character.ac.reset_to_auto' }))
    await waitFor(() => expect(resetOverrideSpy).toHaveBeenCalledWith(7))
  })

  it('unarmored-defense buttons send the chosen ability (or null to disable)', async () => {
    getChar.mockResolvedValue(acChar)
    setUnarmoredSpy.mockResolvedValue(acChar)
    renderWithProviders(<ArmorClass />)
    await screen.findByText('17')

    await userEvent.click(screen.getByRole('button', { name: /character\.ability\.wisdom_short/ }))
    await waitFor(() => expect(setUnarmoredSpy).toHaveBeenCalledWith(7, 'wisdom'))

    await userEvent.click(screen.getByRole('button', { name: 'character.ac.unarmored_off' }))
    await waitFor(() => expect(setUnarmoredSpy).toHaveBeenCalledWith(7, null))
  })

  it('disables the base input while unarmored defense is active', async () => {
    getChar.mockResolvedValue({ ...acChar, unarmored_defense_ability: 'wisdom' })
    renderWithProviders(<ArmorClass />)
    await screen.findByText('17')
    expect(screen.getByPlaceholderText('14')).toBeDisabled()
  })
})

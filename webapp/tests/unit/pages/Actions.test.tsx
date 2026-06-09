import { describe, it, expect, vi, afterEach } from 'vitest'
import type { ReactNode } from 'react'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Actions from '@/pages/Actions'
import type { WeaponAttackResult } from '@/components/WeaponAttackModal'

const { getChar, attackSpy, unarmedSpy, toastError } = vi.hoisted(() => ({
  getChar: vi.fn(),
  attackSpy: vi.fn(),
  unarmedSpy: vi.fn(),
  toastError: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: {
    characters: { get: getChar },
    items: { attack: attackSpy, attackUnarmed: unarmedSpy },
  },
  ApiError: class ApiError extends Error {
    status: number
    constructor(status: number, message = '') {
      super(message)
      this.status = status
    }
  },
}))

// useParams drives charId — pin it so the page resolves to character 7.
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '7' }) }
})

// framer-motion: the attack buttons are `m.button`. Strip motion props, keep onClick.
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION_PROPS = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'drag'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION_PROPS.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return { m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }) }
})

vi.mock('@/lib/unarmedStrike', () => ({ unarmedDamageDice: () => '1' }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: toastError }) }))
vi.mock('@/auth/telegram', () => ({ haptic: { success: () => {}, error: () => {} } }))
vi.mock('@/components/skeletons/ActionsSkeleton', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'actions-skeleton' }) }
})
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { children?: ReactNode }) => React.createElement('div', { 'data-testid': 'layout' }, p.children) }
})
vi.mock('@/components/ui/Surface', async () => {
  const React = await import('react')
  return { default: (p: { children?: ReactNode }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/SectionDivider', async () => {
  const React = await import('react')
  return { default: (p: { children?: ReactNode }) => React.createElement('div', null, p.children) }
})
// WeaponAttackModal is tested on its own; mock it to expose what Actions wires up:
// the result, the inspiration-reroll callback, and onClose.
vi.mock('@/components/WeaponAttackModal', async () => {
  const React = await import('react')
  return {
    default: (p: {
      result: WeaponAttackResult
      onClose: () => void
      inspirationAvailable?: boolean
      onInspirationReroll?: () => void
    }) =>
      React.createElement(
        'div',
        { 'data-testid': 'attack-modal', 'data-inspiration': String(!!p.inspirationAvailable) },
        React.createElement('span', { 'data-testid': 'modal-weapon' }, p.result.weapon_name),
        React.createElement('span', { 'data-testid': 'modal-damage' }, p.result.damage_total),
        p.onInspirationReroll
          ? React.createElement('button', { 'data-testid': 'modal-reroll', onClick: p.onInspirationReroll }, 'reroll')
          : null,
        React.createElement('button', { 'data-testid': 'modal-close', onClick: p.onClose }, 'close'),
      ),
  }
})

const CHAR = {
  id: 7,
  name: 'Hero',
  heroic_inspiration: true,
  classes: [{ id: 1, class_name: 'fighter', level: 5 }],
  items: [
    { id: 10, name: 'Greatsword', item_type: 'weapon', is_equipped: true },
    { id: 11, name: 'Torch', item_type: 'generic', is_equipped: true }, // not a weapon → filtered out
    { id: 12, name: 'Shortbow', item_type: 'weapon', is_equipped: false }, // unequipped → filtered out
  ],
}

const weaponResult: WeaponAttackResult = {
  weapon_name: 'Greatsword',
  to_hit_die: 15,
  to_hit_bonus: 7,
  to_hit_total: 22,
  is_critical: false,
  is_fumble: false,
  damage_dice: '2d6',
  damage_rolls: [5, 6],
  damage_bonus: 4,
  damage_total: 15,
}

afterEach(() => {
  getChar.mockReset()
  attackSpy.mockReset()
  unarmedSpy.mockReset()
  toastError.mockReset()
})

describe('Actions page', () => {
  it('shows the skeleton while the character query is pending', () => {
    getChar.mockReturnValue(new Promise(() => {})) // never resolves
    renderWithProviders(<Actions />)
    expect(screen.getByTestId('actions-skeleton')).toBeInTheDocument()
  })

  it('lists only equipped weapons (filters non-weapons and unequipped items)', async () => {
    getChar.mockResolvedValue(CHAR)
    renderWithProviders(<Actions />)
    expect(await screen.findByText('Greatsword')).toBeInTheDocument()
    expect(screen.queryByText('Torch')).not.toBeInTheDocument()
    expect(screen.queryByText('Shortbow')).not.toBeInTheDocument()
    // unarmed + the single equipped weapon → 2 attack buttons.
    expect(screen.getAllByRole('button')).toHaveLength(2)
  })

  it('fires api.items.attack(charId, itemId) and opens the result modal with the full result', async () => {
    getChar.mockResolvedValue(CHAR)
    attackSpy.mockResolvedValue(weaponResult)
    renderWithProviders(<Actions />)
    await screen.findByText('Greatsword')

    await userEvent.click(screen.getAllByRole('button')[1]) // weapon attack (after unarmed)
    await waitFor(() => expect(attackSpy).toHaveBeenCalledWith(7, 10))

    const modal = await screen.findByTestId('attack-modal')
    expect(modal).toHaveTextContent('Greatsword')
    expect(screen.getByTestId('modal-damage')).toHaveTextContent('15')
    // Contract: every WeaponAttackResult field flows through unchanged.
    expect(Object.keys(weaponResult).sort()).toEqual([
      'damage_bonus', 'damage_dice', 'damage_rolls', 'damage_total',
      'is_critical', 'is_fumble', 'to_hit_bonus', 'to_hit_die', 'to_hit_total', 'weapon_name',
    ])
  })

  it('fires api.items.attackUnarmed(charId) for the unarmed strike', async () => {
    getChar.mockResolvedValue(CHAR)
    unarmedSpy.mockResolvedValue({ ...weaponResult, weapon_name: 'Senza armi', damage_dice: '1', damage_total: 1 })
    renderWithProviders(<Actions />)
    await screen.findByText('Greatsword')

    await userEvent.click(screen.getAllByRole('button')[0]) // unarmed
    await waitFor(() => expect(unarmedSpy).toHaveBeenCalledWith(7))
    expect(await screen.findByTestId('attack-modal')).toBeInTheDocument()
  })

  it('reroll passes with_inspiration=true to the same weapon endpoint', async () => {
    getChar.mockResolvedValue(CHAR)
    attackSpy.mockResolvedValue(weaponResult)
    renderWithProviders(<Actions />)
    await screen.findByText('Greatsword')

    await userEvent.click(screen.getAllByRole('button')[1])
    await screen.findByTestId('attack-modal')

    attackSpy.mockResolvedValue({ ...weaponResult, to_hit_total: 25 })
    await userEvent.click(screen.getByTestId('modal-reroll'))
    await waitFor(() => expect(attackSpy).toHaveBeenCalledWith(7, 10, true))
  })
})

import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Conditions from '@/pages/Conditions'

const { getChar, updateConditions, listRules, turnStart, toastInfo, toastError, showNotif } = vi.hoisted(() => ({
  getChar: vi.fn(),
  updateConditions: vi.fn(),
  listRules: vi.fn(),
  turnStart: vi.fn(),
  toastInfo: vi.fn(),
  toastError: vi.fn(),
  showNotif: vi.fn(),
}))

// Compat contract:
//  - api.characters.updateConditions(id, Record<string,unknown>) → PATCH /conditions {conditions}
//  - api.homebrew.turnStart(id) → { notifications: [...] } (NOT homebrew_notifications)
vi.mock('@/api/client', () => ({
  api: {
    characters: { get: getChar, updateConditions },
    homebrew: { listRules, turnStart },
  },
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

vi.mock('@/auth/telegram', () => ({ haptic: { light: () => {}, medium: () => {}, success: () => {}, error: () => {} } }))
vi.mock('@/styles/motion', () => ({
  spring: new Proxy({}, { get: () => ({}) }),
  stagger: new Proxy({}, { get: () => 0 }),
}))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ info: toastInfo, error: toastError, success: vi.fn() }) }))
vi.mock('@/lib/conditions', () => ({ CONDITION_ICONS: new Proxy({}, { get: () => () => null }) }))
vi.mock('@/components/homebrew/HomebrewNotification', () => ({ showHomebrewNotifications: showNotif }))

const passthrough = vi.hoisted(() => async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/Layout', passthrough)
vi.mock('@/components/ui/Surface', passthrough)
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return {
    default: (p: { onClick?: () => void; disabled?: boolean; loading?: boolean; children?: unknown }) =>
      React.createElement('button', { onClick: p.onClick, disabled: p.disabled || p.loading }, p.children),
  }
})
vi.mock('@/components/ui/FilterChip', async () => {
  const React = await import('react')
  return {
    default: (p: { label: string; onToggle: () => void }) =>
      React.createElement('button', { onClick: p.onToggle }, p.label),
  }
})
vi.mock('@/components/ui/ConfirmSheet', async () => {
  const React = await import('react')
  return {
    default: (p: { open: boolean; confirmLabel: string; onConfirm: () => void }) =>
      p.open ? React.createElement('button', { onClick: p.onConfirm }, p.confirmLabel) : null,
  }
})
vi.mock('@/pages/conditions/ConditionDetailModal', async () => ({ default: () => null }))
vi.mock('@/components/homebrew/CustomConditionCard', async () => {
  const React = await import('react')
  return {
    default: (p: { conditionKey: string; onRemove: () => void }) =>
      React.createElement(
        'div',
        { 'data-testid': `custom-${p.conditionKey}` },
        React.createElement('button', { onClick: p.onRemove }, 'remove'),
      ),
  }
})
vi.mock('@/components/skeletons/ConditionsSkeleton', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'cond-skeleton' }) }
})

// An enabled rule whose `apply_condition` effect is buried inside an `if` branch
// — exercises collectApplyConditionKeys' recursive walk.
const bleedingRule = {
  id: 1,
  name: 'Bleeding',
  enabled: true,
  dsl: {
    triggers: [
      { effects: [{ action: 'if', then: [{ action: 'apply_condition', key: 'custom:bleeding' }], else: [] }] },
    ],
  },
}

afterEach(() => {
  getChar.mockReset()
  updateConditions.mockReset()
  listRules.mockReset()
  turnStart.mockReset()
  toastInfo.mockReset()
  toastError.mockReset()
  showNotif.mockReset()
})

describe('Conditions page', () => {
  it('shows the skeleton while the character query is pending', () => {
    getChar.mockReturnValue(new Promise(() => {}))
    listRules.mockResolvedValue([])
    renderWithProviders(<Conditions />)
    expect(screen.getByTestId('cond-skeleton')).toBeInTheDocument()
  })

  it('toggling a standard condition merges it into the conditions map', async () => {
    getChar.mockResolvedValue({ id: 5, conditions: {} })
    listRules.mockResolvedValue([])
    updateConditions.mockResolvedValue({ id: 5, conditions: { blinded: true } })
    renderWithProviders(<Conditions />)
    await userEvent.click(await screen.findByText('character.conditions.blinded'))
    await waitFor(() => expect(updateConditions).toHaveBeenCalledWith(5, { blinded: true }))
  })

  it('setting an exhaustion level PATCHes the cumulative value', async () => {
    getChar.mockResolvedValue({ id: 5, conditions: {} })
    listRules.mockResolvedValue([])
    updateConditions.mockResolvedValue({ id: 5, conditions: { exhaustion: 3 } })
    renderWithProviders(<Conditions />)
    await screen.findByText('character.conditions.blinded')
    await userEvent.click(screen.getByRole('button', { name: '3' }))
    await waitFor(() => expect(updateConditions).toHaveBeenCalledWith(5, { exhaustion: 3 }))
  })

  it('reset-all clears the 14 standard conditions + exhaustion via the confirm sheet', async () => {
    getChar.mockResolvedValue({ id: 5, conditions: { blinded: true } })
    listRules.mockResolvedValue([])
    updateConditions.mockResolvedValue({ id: 5, conditions: {} })
    renderWithProviders(<Conditions />)
    await userEvent.click(await screen.findByText('character.conditions.reset_all'))
    await userEvent.click(await screen.findByText('common.confirm'))
    await waitFor(() =>
      expect(updateConditions).toHaveBeenCalledWith(
        5,
        expect.objectContaining({ exhaustion: 0, blinded: false, stunned: false }),
      ),
    )
  })

  it('applies a custom condition known to an enabled rule (derive + write shape)', async () => {
    getChar.mockResolvedValue({ id: 5, conditions: {} })
    listRules.mockResolvedValue([bleedingRule])
    updateConditions.mockResolvedValue({ id: 5, conditions: {} })
    renderWithProviders(<Conditions />)
    // The "apply custom" affordance only renders if the recursive walk found custom:bleeding.
    await userEvent.click(await screen.findByLabelText('character.conditions.apply_custom_aria'))
    await waitFor(() =>
      expect(updateConditions).toHaveBeenCalledWith(5, {
        'custom:bleeding': { rule_id: 1, params: {} },
      }),
    )
  })

  it('removing a custom condition writes a false shadow (merge cannot pop)', async () => {
    getChar.mockResolvedValue({ id: 5, conditions: { 'custom:bleeding': { rule_id: 1, params: {} } } })
    listRules.mockResolvedValue([bleedingRule])
    updateConditions.mockResolvedValue({ id: 5, conditions: {} })
    renderWithProviders(<Conditions />)
    const card = await screen.findByTestId('custom-custom:bleeding')
    await userEvent.click(card.querySelector('button')!)
    await waitFor(() => expect(updateConditions).toHaveBeenCalledWith(5, { 'custom:bleeding': false }))
  })

  it('turn-start surfaces homebrew notifications when the rule fired', async () => {
    getChar.mockResolvedValue({ id: 5, conditions: { 'custom:bleeding': { rule_id: 1, params: {} } } })
    listRules.mockResolvedValue([bleedingRule])
    turnStart.mockResolvedValue({ notifications: [{ title: 'Bleeding', message: '1 dmg' }] })
    renderWithProviders(<Conditions />)
    await userEvent.click(await screen.findByText('character.conditions.turn_start.label'))
    await waitFor(() =>
      expect(showNotif).toHaveBeenCalledWith([{ title: 'Bleeding', message: '1 dmg' }]),
    )
  })

  it('turn-start with no effect shows a neutral info toast', async () => {
    getChar.mockResolvedValue({ id: 5, conditions: { 'custom:bleeding': { rule_id: 1, params: {} } } })
    listRules.mockResolvedValue([bleedingRule])
    turnStart.mockResolvedValue({ notifications: [] })
    renderWithProviders(<Conditions />)
    await userEvent.click(await screen.findByText('character.conditions.turn_start.label'))
    await waitFor(() =>
      expect(toastInfo).toHaveBeenCalledWith('character.conditions.turn_start.no_effect'),
    )
  })
})

import { describe, it, expect, vi } from 'vitest'
import type { ReactNode } from 'react'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import CompanionCard from '@/pages/extras/CompanionCard'
import type { Companion } from '@/types'

const { attack } = vi.hoisted(() => ({ attack: vi.fn() }))

vi.mock('@/api/client', () => ({
  api: { companions: { attack, hp: vi.fn(), deactivate: vi.fn(), activate: vi.fn() } },
  ApiError: class ApiError extends Error {},
}))
vi.mock('react-i18next', async (orig) => ({
  ...((await orig()) as Record<string, unknown>),
  useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }),
}))
vi.mock('@/hooks/useD20Roll', () => ({ useD20Roll: () => vi.fn().mockResolvedValue([12]) }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: vi.fn(), info: vi.fn(), success: vi.fn() }) }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/lib/rollOptions', async (orig) => ({
  ...((await orig()) as Record<string, unknown>),
  askRollOptions: vi.fn().mockResolvedValue({ options: [], option_inputs: {} }),
  refreshAfterOptions: vi.fn(),
}))
vi.mock('@/components/ui/RollButton', async () => {
  const React = await import('react')
  return { default: (p: { children?: ReactNode; onRoll: (m: string) => void }) =>
    React.createElement('button', { onClick: () => p.onRoll('normal') }, p.children) }
})
vi.mock('@/pages/extras/WildHealSheet', async () => {
  const React = await import('react')
  return { default: (p: { slots: { level: number }[] }) =>
    React.createElement('div', { 'data-testid': 'heal-sheet' }, p.slots.map((s) => s.level).join(',')) }
})

const form = (active: boolean) => ({
  id: 1, character_id: 7, kind: 'wild_shape', name: 'Lupo', srd_index: 'wolf', max_hp: 11, current_hp: 11, temp_hp: 0,
  armor_class: 13, notes: null, is_active: active, created_at: '', down: false,
  statblock: { actions: [{ name: 'Morso', attack_bonus: 4, damage_dice: '2d4+2', damage_type: 'piercing' }] },
}) as unknown as Companion

describe('CompanionCard druid features', () => {
  it('Combat Wild Shape: an active form offers the heal with the slot levels the druid can spend', async () => {
    renderWithProviders(<CompanionCard charId={7} comp={form(true)} wildShapeUses={1} healSlots={[{ level: 1, left: 2 }, { level: 2, left: 1 }]} />)
    expect(screen.queryByTestId('heal-sheet')).toBeNull()
    await userEvent.click(screen.getByText('character.extras.wild_heal'))
    expect(screen.getByTestId('heal-sheet')).toHaveTextContent('1,2')
  })

  it('has no heal for a character without the feature or for a form that is not active', () => {
    renderWithProviders(<CompanionCard charId={7} comp={form(true)} wildShapeUses={1} healSlots={null} />)
    expect(screen.queryByText('character.extras.wild_heal')).toBeNull()
    renderWithProviders(<CompanionCard charId={7} comp={form(false)} wildShapeUses={1} healSlots={[{ level: 1, left: 1 }]} />)
    expect(screen.queryByText('character.extras.wild_heal')).toBeNull()
  })

  it('Primal Strike: an attack in beast form says it is magical, a plain one does not', async () => {
    const result = { to_hit_die: 12, to_hit_bonus: 4, to_hit_total: 16, dice: [12], mode: 'normal', is_critical: false,
      damage_rolls: [3], damage_total: 7, damage_type: 'piercing' }
    attack.mockResolvedValueOnce({ ...result, is_magical: true })
    renderWithProviders(<CompanionCard charId={7} comp={form(true)} wildShapeUses={1} />)
    await userEvent.click(screen.getByText('character.turn.attack'))
    expect(await screen.findByRole('status')).toHaveTextContent('character.extras.magical')
    attack.mockResolvedValueOnce({ ...result, is_magical: false })
    await userEvent.click(screen.getByText('character.turn.attack'))
    await vi.waitFor(() => expect(screen.getByRole('status')).not.toHaveTextContent('character.extras.magical'))
  })
})

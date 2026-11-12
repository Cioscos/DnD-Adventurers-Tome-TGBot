import { describe, it, expect, vi } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { renderWithProviders } from '../../utils/renderWithProviders'
import AddMonsterSheet from '@/pages/session/AddMonsterSheet'

vi.mock('@/api/client', () => ({ api: { sessions: { encounter: { addCombatants: vi.fn() } } } }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})

const confirm = () => screen.getByRole('button', { name: 'session.combat.add_confirm' })

describe('AddMonsterSheet', () => {
  it('in full mode the monster needs max HP, otherwise it would show as dead', () => {
    renderWithProviders(<AddMonsterSheet sessionId={1} mode="full" onClose={() => {}} />)
    fireEvent.change(screen.getByPlaceholderText('session.combat.monster_name_placeholder'), { target: { value: 'Goblin' } })
    expect(confirm()).toBeDisabled()
    fireEvent.change(screen.getByPlaceholderText('7'), { target: { value: '7' } })
    expect(confirm()).toBeEnabled()
  })

  it('in light mode the name alone is enough', () => {
    renderWithProviders(<AddMonsterSheet sessionId={1} mode="light" onClose={() => {}} />)
    fireEvent.change(screen.getByPlaceholderText('session.combat.monster_name_placeholder'), { target: { value: 'Goblin' } })
    expect(confirm()).toBeEnabled()
  })
})

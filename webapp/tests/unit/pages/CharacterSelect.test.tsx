import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import CharacterSelect from '@/pages/CharacterSelect'

const { list, me, navigateSpy } = vi.hoisted(() => ({ list: vi.fn(), me: vi.fn(), navigateSpy: vi.fn() }))

vi.mock('@/api/client', () => ({ api: { characters: { list }, sessions: { me } } }))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useNavigate: () => navigateSpy }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({
  haptic: new Proxy({}, { get: () => () => {} }),
  telegramConfirm: vi.fn(),
}))
vi.mock('@/components/ui/Surface', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown; onClick?: () => void }) => React.createElement('div', { onClick: p.onClick }, p.children) }
})
vi.mock('@/components/ui/Reveal', async () => {
  const React = await import('react')
  return { default: { Stagger: (p: { children?: unknown }) => React.createElement('div', null, p.children), Item: (p: { children?: unknown }) => React.createElement('div', null, p.children) } }
})
vi.mock('@/components/ui/HPGauge', () => ({ default: () => null }))
vi.mock('@/components/ui/Sheet', () => ({ default: () => null }))
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void; children?: unknown }) => React.createElement('button', { onClick: p.onClick }, p.children) }
})

const char = (over: Record<string, unknown> = {}) => ({
  id: 1, name: 'Aragorn', hit_points: 20, current_hit_points: 10, temp_hp: 0, ac: 15,
  total_level: 1, class_summary: 'Ranger', heroic_inspiration: false, experience_points: 0,
  hp_max_homebrew_modifier: 0, ac_homebrew_modifier: 0, is_dead: false, ...over,
})

afterEach(() => { list.mockReset(); me.mockReset(); navigateSpy.mockReset() })

describe('CharacterSelect', () => {
  it('shows resume session when a session is active', async () => {
    list.mockResolvedValue([char()])
    me.mockResolvedValue({ id: 7, status: 'active' })
    renderWithProviders(<CharacterSelect />)
    await userEvent.click(await screen.findByRole('button', { name: 'session.resume' }))
    expect(navigateSpy).toHaveBeenCalledWith('/session/7')
  })

  it('shows plain session button otherwise', async () => {
    list.mockResolvedValue([char()])
    me.mockResolvedValue(null)
    renderWithProviders(<CharacterSelect />)
    await userEvent.click(await screen.findByRole('button', { name: 'session.title' }))
    expect(navigateSpy).toHaveBeenCalledWith('/session')
  })

  it('treats a failed session query as no session', async () => {
    list.mockResolvedValue([char()])
    me.mockRejectedValue(new Error('boom'))
    renderWithProviders(<CharacterSelect />)
    expect(await screen.findByRole('button', { name: 'session.title' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'session.resume' })).toBeNull()
  })

  it('home adds homebrew to hp and ac', async () => {
    list.mockResolvedValue([char({ hit_points: 20, hp_max_homebrew_modifier: 5, ac: 15, ac_homebrew_modifier: 2 })])
    me.mockResolvedValue(null)
    renderWithProviders(<CharacterSelect />)
    expect(await screen.findByText(/\/25/)).toBeTruthy()
    expect(screen.getByText('17')).toBeTruthy()
  })

  it('shows dead and unconfigured badges', async () => {
    list.mockResolvedValue([
      char({ id: 1, name: 'Morto', is_dead: true, current_hit_points: 0 }),
      char({ id: 2, name: 'Nuovo', hit_points: 0, current_hit_points: 0 }),
    ])
    me.mockResolvedValue(null)
    renderWithProviders(<CharacterSelect />)
    expect(await screen.findByText('character.select.dead_badge')).toBeTruthy()
    expect(screen.getByText('character.select.unconfigured_badge')).toBeTruthy()
    expect(screen.queryByText('character.select.unconscious_badge')).toBeNull()
  })
})

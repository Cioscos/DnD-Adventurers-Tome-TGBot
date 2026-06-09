import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Session from '@/pages/Session'

const { me, list, create, navigateSpy } = vi.hoisted(() => ({ me: vi.fn(), list: vi.fn(), create: vi.fn(), navigateSpy: vi.fn() }))

vi.mock('@/api/client', () => ({ api: { sessions: { me, create }, characters: { list } } }))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useNavigate: () => navigateSpy }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/Surface', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/FancyHeader', async () => {
  const React = await import('react')
  return { default: (p: { title?: unknown }) => React.createElement('div', null, p.title) }
})
vi.mock('@/components/ui/Reveal', async () => {
  const React = await import('react')
  return { default: { Stagger: (p: { children?: unknown }) => React.createElement('div', null, p.children), Item: (p: { children?: unknown }) => React.createElement('div', null, p.children) } }
})
vi.mock('@/components/ui/Skeleton', async () => {
  const React = await import('react')
  const S = () => React.createElement('div', { 'data-testid': 'skeleton' })
  return { default: { Line: S, Rect: S, Circle: S } }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void; disabled?: boolean; loading?: boolean; children?: unknown }) => React.createElement('button', { onClick: p.onClick, disabled: p.disabled || p.loading }, p.children) }
})

afterEach(() => { me.mockReset(); list.mockReset(); create.mockReset(); navigateSpy.mockReset() })

describe('Session', () => {
  it('resumes an active session', async () => {
    me.mockResolvedValue({ id: 5, code: 'ABCDEF', gm_user_id: 1, title: 'La Cripta', participants: [{ role: 'game_master', user_id: 1 }] })
    list.mockResolvedValue([])
    renderWithProviders(<Session />)
    await userEvent.click(await screen.findByRole('button', { name: 'session.resume' }))
    expect(navigateSpy).toHaveBeenCalledWith('/session/5')
  })

  it('offers create + join on the landing when there is no active session', async () => {
    me.mockResolvedValue(null)
    list.mockResolvedValue([{ id: 7, name: 'Aragorn', class_summary: 'Ranger' }])
    create.mockResolvedValue({ id: 9 })
    renderWithProviders(<Session />)
    const createBtn = await screen.findByRole('button', { name: 'session.create_button' })
    expect(screen.getByRole('button', { name: 'session.join_button' })).toBeEnabled()
    await userEvent.click(createBtn)
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
  })

  it('disables join when the player has no characters', async () => {
    me.mockResolvedValue(null)
    list.mockResolvedValue([])
    renderWithProviders(<Session />)
    expect(await screen.findByRole('button', { name: 'session.join_button' })).toBeDisabled()
  })
})

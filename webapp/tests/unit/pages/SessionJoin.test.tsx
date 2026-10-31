import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import SessionJoin from '@/pages/SessionJoin'

const { list, join, navigateSpy } = vi.hoisted(() => ({ list: vi.fn(), join: vi.fn(), navigateSpy: vi.fn() }))

vi.mock('@/api/client', () => ({ api: { characters: { list }, sessions: { join } }, ApiError: class ApiError extends Error { detail: unknown; constructor(d: unknown) { super('e'); this.detail = d } } }))
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
vi.mock('@/components/ui/Skeleton', async () => {
  const React = await import('react')
  const S = () => React.createElement('div', { 'data-testid': 'skeleton' })
  return { default: { Line: S, Rect: S, Circle: S } }
})
vi.mock('@/components/ui/Input', async () => {
  const React = await import('react')
  return { default: (p: { label?: string; value: string; onChange: (v: string) => void }) => React.createElement('input', { 'aria-label': p.label, value: p.value, onChange: (e: { target: { value: string } }) => p.onChange(e.target.value) }) }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void; disabled?: boolean; loading?: boolean; children?: unknown }) => React.createElement('button', { onClick: p.onClick, disabled: p.disabled || p.loading }, p.children) }
})

afterEach(() => { list.mockReset(); join.mockReset(); navigateSpy.mockReset() })

describe('SessionJoin', () => {
  it('keeps join disabled until a 6-char code is entered and a character is picked', async () => {
    list.mockResolvedValue([{ id: 7, name: 'Aragorn', class_summary: 'Ranger' }, { id: 8, name: 'Gimli', class_summary: 'Fighter' }])
    renderWithProviders(<SessionJoin />)
    const joinBtn = await screen.findByRole('button', { name: 'session.join_button' })
    expect(joinBtn).toBeDisabled()
    fireEvent.change(screen.getByLabelText('session.code_label'), { target: { value: 'ABCDEF' } })
    expect(joinBtn).toBeDisabled()
    await userEvent.click(screen.getByText('Gimli'))
    expect(joinBtn).toBeEnabled()
  })

  it('with a single character and a valid code it auto-joins with the uppercased code', async () => {
    list.mockResolvedValue([{ id: 7, name: 'Aragorn', class_summary: 'Ranger' }])
    join.mockResolvedValue({ id: 3 })
    renderWithProviders(<SessionJoin />)
    await screen.findByRole('button', { name: 'session.join_button' })
    fireEvent.change(screen.getByLabelText('session.code_label'), { target: { value: 'abcdef' } })
    await waitFor(() => expect(join).toHaveBeenCalledWith('ABCDEF', 7))
    await waitFor(() => expect(navigateSpy).toHaveBeenCalledWith('/session/3', { replace: true }))
  })

  it('with several characters it joins with the picked one on tap', async () => {
    list.mockResolvedValue([{ id: 7, name: 'Aragorn', class_summary: 'Ranger' }, { id: 8, name: 'Gimli', class_summary: 'Fighter' }])
    join.mockResolvedValue({ id: 3 })
    renderWithProviders(<SessionJoin />)
    await screen.findByRole('button', { name: 'session.join_button' })
    fireEvent.change(screen.getByLabelText('session.code_label'), { target: { value: 'abcdef' } })
    await userEvent.click(screen.getByText('Gimli'))
    await userEvent.click(screen.getByRole('button', { name: 'session.join_button' }))
    await waitFor(() => expect(join).toHaveBeenCalledWith('ABCDEF', 8))
  })

  it('failed character fetch shows offline unavailable, not "create a character"', async () => {
    list.mockRejectedValue(new TypeError('Failed to fetch'))
    renderWithProviders(<SessionJoin />)
    expect(await screen.findByText('common.offline_unavailable')).toBeInTheDocument()
    expect(screen.queryByText('session.join_needs_character')).not.toBeInTheDocument()
  })
})

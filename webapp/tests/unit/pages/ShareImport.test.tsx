import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../utils/renderWithProviders'
import ShareImport from '@/pages/ShareImport'

const { getShare, list } = vi.hoisted(() => ({ getShare: vi.fn(), list: vi.fn() }))

vi.mock('@/api/client', () => {
  class ApiError extends Error {
    constructor(public status: number, public detail: unknown) { super(`API ${status}`) }
  }
  return { api: { share: { get: getShare }, characters: { list } }, ApiError }
})
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ token: 'tok' }), useNavigate: () => vi.fn() }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/store/characterStore', () => ({ useCharacterStore: (sel: (s: { lastCharId: null }) => unknown) => sel({ lastCharId: null }) }))
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})

const preview = { kind: 'item', title: 'Spada', sender_char_name: 'Bob', is_voice: false }

afterEach(() => { getShare.mockReset(); list.mockReset() })

describe('ShareImport', () => {
  it('failed character fetch shows offline unavailable, not "create a character"', async () => {
    getShare.mockResolvedValue(preview)
    list.mockRejectedValue(new TypeError('Failed to fetch'))
    renderWithProviders(<ShareImport />)
    expect(await screen.findByText('common.offline_unavailable')).toBeInTheDocument()
    expect(screen.queryByText('share.import.needs_character')).not.toBeInTheDocument()
  })

  it('asks to create a character only when there really are none', async () => {
    getShare.mockResolvedValue(preview)
    list.mockResolvedValue([])
    renderWithProviders(<ShareImport />)
    expect(await screen.findByText('share.import.needs_character')).toBeInTheDocument()
  })
})

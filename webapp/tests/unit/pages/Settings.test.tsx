import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { render } from '@testing-library/react'
import Settings from '@/pages/Settings'

const { getChar, deleteChar, retentionPreview, navigateSpy, toastError } = vi.hoisted(() => ({
  getChar: vi.fn(),
  deleteChar: vi.fn(),
  retentionPreview: vi.fn(),
  navigateSpy: vi.fn(),
  toastError: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: {
    characters: { get: getChar, delete: deleteChar, update: vi.fn(), recalcHp: vi.fn() },
    history: { retentionPreview },
  },
}))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '5' }), useNavigate: () => navigateSpy }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return {
    ...actual,
    useTranslation: () => ({
      t: (k: string, o?: { name?: string }) => (o?.name ? `${k}|${o.name}` : k),
      i18n: { language: 'it', changeLanguage: vi.fn() },
    }),
  }
})
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: toastError, success: vi.fn() }) }))
vi.mock('@/auth/telegram', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, haptic: new Proxy({}, { get: () => () => {} }) }
})
vi.mock('@/dice/packs/dicePackContext', () => ({ useDicePack: () => ({ loading: false, error: null }) }))
vi.mock('@/dice/packs/manifest', () => ({ loadManifest: async () => ({ name: 'x' }) }))
vi.mock('@/components/Layout', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/ConfirmSheet', async () => {
  const React = await import('react')
  return {
    default: (p: { open: boolean; title: string; body?: string; confirmLabel: string; onConfirm: () => void }) =>
      p.open
        ? React.createElement('div', { 'data-testid': `sheet-${p.title}` }, p.body,
            React.createElement('button', { onClick: p.onConfirm }, `${p.title}::${p.confirmLabel}`))
        : null,
  }
})

const char = { id: 5, name: 'Aragorn', settings: {}, spellcasting: null }

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  qc.setQueryData(['characters'], [{ id: 5, name: 'Aragorn' }, { id: 6, name: 'Boromir' }])
  const utils = render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Settings />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { qc, ...utils }
}

afterEach(() => {
  getChar.mockReset(); deleteChar.mockReset(); retentionPreview.mockReset()
  navigateSpy.mockReset(); toastError.mockReset()
})

describe('Settings delete character', () => {
  const arrange = () => {
    getChar.mockResolvedValue(char)
    retentionPreview.mockResolvedValue({ total: 0, would_purge_events: 0, would_purge_days: 0 })
    return setup()
  }

  it('delete asks confirmation naming the character', async () => {
    arrange()
    await userEvent.click(await screen.findByRole('button', { name: 'character.settings.delete_character' }))
    expect(screen.getByText('character.select.delete_confirm|Aragorn')).toBeTruthy()
    expect(deleteChar).not.toHaveBeenCalled()
  })

  it('confirming deletes, cleans cache and goes home', async () => {
    deleteChar.mockResolvedValue(undefined)
    const { qc } = arrange()
    const removeSpy = vi.spyOn(qc, 'removeQueries')
    await userEvent.click(await screen.findByRole('button', { name: 'character.settings.delete_character' }))
    await userEvent.click(screen.getByRole('button', { name: /::common\.delete$/ }))
    await waitFor(() => expect(navigateSpy).toHaveBeenCalledWith('/', { replace: true }))
    expect(deleteChar).toHaveBeenCalledWith(5)
    expect(removeSpy).toHaveBeenCalledWith({ queryKey: ['character', 5] })
    expect(qc.getQueryData(['characters'])).toEqual([{ id: 6, name: 'Boromir' }])
  })

  it('failure shows delete_failed and stays', async () => {
    deleteChar.mockRejectedValue(new Error('boom'))
    arrange()
    await userEvent.click(await screen.findByRole('button', { name: 'character.settings.delete_character' }))
    await userEvent.click(screen.getByRole('button', { name: /::common\.delete$/ }))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('character.select.delete_failed'))
    expect(navigateSpy).not.toHaveBeenCalled()
  })
})

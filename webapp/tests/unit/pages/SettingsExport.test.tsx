import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor, render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import Settings from '@/pages/Settings'
import CharacterSelect from '@/pages/CharacterSelect'

const m = vi.hoisted(() => ({
  getChar: vi.fn(), list: vi.fn(), me: vi.fn(), exportChar: vi.fn(), exportSend: vi.fn(),
  duplicate: vi.fn(), importChar: vi.fn(), navigateSpy: vi.fn(), toastError: vi.fn(), toastSuccess: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: {
    characters: {
      get: m.getChar, list: m.list, delete: vi.fn(), update: vi.fn(), recalcHp: vi.fn(),
      export: m.exportChar, exportSend: m.exportSend, duplicate: m.duplicate, import: m.importChar,
    },
    history: { retentionPreview: vi.fn() },
    sessions: { me: m.me },
  },
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: unknown) { super('x') }
  },
}))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useParams: () => ({ id: '5' }), useNavigate: () => m.navigateSpy }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it', changeLanguage: vi.fn() } }) }
})
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: m.toastError, success: m.toastSuccess }) }))
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
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', null, p.children) : null) }
})

const char = { id: 5, name: 'Aragorn', settings: {}, spellcasting: null }

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const spy = vi.spyOn(qc, 'invalidateQueries')
  render(<QueryClientProvider client={qc}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>)
  return { qc, spy }
}

afterEach(() => {
  Object.values(m).forEach((f) => f.mockReset())
  vi.restoreAllMocks()
})

describe('Settings export / duplicate', () => {
  const open = async () => {
    m.getChar.mockResolvedValue(char)
    const r = wrap(<Settings />)
    await userEvent.click(await screen.findByText('character.settings.transfer.export'))
    return r
  }

  it('opens a sheet with send and download actions', async () => {
    await open()
    expect(screen.getByText('character.settings.transfer.send')).toBeTruthy()
    expect(screen.getByText('character.settings.transfer.download')).toBeTruthy()
  })

  it('shows a success toast after sending to Telegram', async () => {
    m.exportSend.mockResolvedValue({ ok: true })
    await open()
    await userEvent.click(screen.getByText('character.settings.transfer.send'))
    await waitFor(() => expect(m.toastSuccess).toHaveBeenCalledWith('character.settings.transfer.sent'))
    expect(m.exportSend).toHaveBeenCalledWith(5)
  })

  it('on 503 explains that only download is available', async () => {
    const { ApiError } = await import('@/api/client')
    m.exportSend.mockRejectedValue(new ApiError(503, 'Bot not configured'))
    await open()
    await userEvent.click(screen.getByText('character.settings.transfer.send'))
    expect(await screen.findByText('character.settings.transfer.download_only')).toBeTruthy()
    expect(screen.getByText('character.settings.transfer.download')).toBeTruthy()
  })

  it('downloads the exported JSON through a temporary anchor', async () => {
    m.exportChar.mockResolvedValue({ format_version: 1 })
    const createUrl = vi.fn(() => 'blob:x')
    Object.assign(URL, { createObjectURL: createUrl, revokeObjectURL: vi.fn() })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await open()
    await userEvent.click(screen.getByText('character.settings.transfer.download'))
    await waitFor(() => expect(click).toHaveBeenCalled())
    expect(m.exportChar).toHaveBeenCalledWith(5)
    expect(createUrl).toHaveBeenCalled()
  })

  it('duplicate navigates to the new character and refreshes the list', async () => {
    m.getChar.mockResolvedValue(char)
    m.duplicate.mockResolvedValue({ id: 9 })
    const { spy } = wrap(<Settings />)
    await userEvent.click(await screen.findByText('character.settings.transfer.duplicate'))
    await waitFor(() => expect(m.navigateSpy).toHaveBeenCalledWith('/char/9'))
    expect(spy).toHaveBeenCalledWith({ queryKey: ['characters'] })
  })
})

describe('CharacterSelect import', () => {
  const pick = async () => {
    m.list.mockResolvedValue([])
    m.me.mockResolvedValue(null)
    wrap(<CharacterSelect />)
    await screen.findByText('character.select.import')
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    expect(input.accept).toBe('.json,application/json')
    await userEvent.upload(input, new File(['{}'], 'c.json', { type: 'application/json' }))
  }

  it('navigates to the imported character', async () => {
    m.importChar.mockResolvedValue({ id: 12 })
    await pick()
    await waitFor(() => expect(m.navigateSpy).toHaveBeenCalledWith('/char/12'))
  })

  it('shows the server detail on 413/422', async () => {
    const { ApiError } = await import('@/api/client')
    m.importChar.mockRejectedValue(new ApiError(413, 'File too large'))
    await pick()
    await waitFor(() => expect(m.toastError).toHaveBeenCalledWith('File too large'))
  })

  it('shows the pydantic messages with their field on a 422 list detail', async () => {
    const { ApiError } = await import('@/api/client')
    m.importChar.mockRejectedValue(new ApiError(422, [{ loc: ['body', 'hit_points'], msg: 'must be >= 0' }]))
    await pick()
    await waitFor(() => expect(m.toastError).toHaveBeenCalledWith('hit_points: must be >= 0'))
  })

  it('falls back to the generic text when the detail is unusable', async () => {
    const { ApiError } = await import('@/api/client')
    m.importChar.mockRejectedValue(new ApiError(422, [{}]))
    await pick()
    await waitFor(() => expect(m.toastError).toHaveBeenCalledWith('character.select.import_failed'))
  })
})

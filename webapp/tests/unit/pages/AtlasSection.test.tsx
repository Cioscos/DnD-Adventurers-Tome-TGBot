import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import AtlasSection from '@/pages/campaign/AtlasSection'

const { maps, uploadMap, navigateSpy, downscale, toastError } = vi.hoisted(() => ({
  maps: vi.fn(), uploadMap: vi.fn(), navigateSpy: vi.fn(), downscale: vi.fn(), toastError: vi.fn(),
}))

vi.mock('@/api/client', () => ({
  api: { atlas: { maps, uploadMap } },
  ApiError: class ApiError extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))
vi.mock('@/lib/downscaleImage', () => ({ downscaleImage: downscale }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: toastError, success: vi.fn() }) }))
vi.mock('react-router-dom', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useNavigate: () => navigateSpy }
})
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/components/ui/Sheet', () => ({
  default: ({ open, children }: { open: boolean; children: React.ReactNode }) => (open ? <div>{children}</div> : null),
}))

const map = (over = {}) => ({ id: 9, name: 'Faerûn', revealed: false, revealed_at: null, updated_at: 'x', marker_count: 2, ...over })
afterEach(() => { maps.mockReset(); uploadMap.mockReset(); navigateSpy.mockReset(); downscale.mockReset(); toastError.mockReset() })

describe('AtlasSection', () => {
  it('shows hidden badge only to the GM', async () => {
    maps.mockResolvedValue([map()])
    const { unmount } = renderWithProviders(<AtlasSection campaignId={3} isGm />)
    expect(await screen.findByText('atlas.hidden')).toBeTruthy()
    expect(screen.getByRole('button', { name: /atlas.upload/ })).toBeTruthy()
    unmount()
    renderWithProviders(<AtlasSection campaignId={3} isGm={false} />)
    expect(await screen.findByText('Faerûn')).toBeTruthy()
    expect(screen.queryByText('atlas.hidden')).toBeNull()
    expect(screen.queryByRole('button', { name: /atlas.upload/ })).toBeNull()
  })

  it('player empty state', async () => {
    maps.mockResolvedValue([])
    renderWithProviders(<AtlasSection campaignId={3} isGm={false} />)
    expect(await screen.findByText('atlas.empty_player')).toBeTruthy()
  })

  it('tap navigates to map route', async () => {
    maps.mockResolvedValue([map({ revealed: true })])
    renderWithProviders(<AtlasSection campaignId={3} isGm={false} />)
    await userEvent.click(await screen.findByText('Faerûn'))
    expect(navigateSpy).toHaveBeenCalledWith('/campaign/3/atlas/9')
  })

  it('upload downscales then posts FormData with name', async () => {
    maps.mockResolvedValue([])
    const small = new File(['s'], 'small.webp', { type: 'image/webp' })
    downscale.mockResolvedValue(small)
    uploadMap.mockResolvedValue(map())
    const { container } = renderWithProviders(<AtlasSection campaignId={3} isGm />)
    await userEvent.click(await screen.findByRole('button', { name: /atlas.upload/ }))
    await userEvent.type(screen.getByRole('textbox'), 'Mappa')
    const input = container.querySelector('input[type=file]') as HTMLInputElement
    await userEvent.upload(input, new File(['big'], 'big.png', { type: 'image/png' }))
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    await waitFor(() => expect(uploadMap).toHaveBeenCalled())
    expect(downscale).toHaveBeenCalled()
    const fd = uploadMap.mock.calls[0][1] as FormData
    expect(uploadMap.mock.calls[0][0]).toBe(3)
    expect(fd.get('name')).toBe('Mappa')
    expect((fd.get('file') as File).name).toBe('small.webp')
  })

  it('shows a toast when the image cannot be decoded', async () => {
    maps.mockResolvedValue([])
    downscale.mockRejectedValue(new Error('decode'))
    const { container } = renderWithProviders(<AtlasSection campaignId={3} isGm />)
    await userEvent.click(await screen.findByRole('button', { name: /atlas.upload/ }))
    await userEvent.type(screen.getByRole('textbox'), 'M')
    await userEvent.upload(container.querySelector('input[type=file]') as HTMLInputElement, new File(['x'], 'b.png', { type: 'image/png' }))
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('atlas.err_image'))
    expect(uploadMap).not.toHaveBeenCalled()
  })
})

import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import LoreEditorSheet from '@/pages/campaign/LoreEditorSheet'
import type { LoreRead } from '@/types'

const { create, update } = vi.hoisted(() => ({ create: vi.fn(), update: vi.fn() }))

vi.mock('@/api/client', () => ({
  api: { lore: { create, update } },
  ApiError: class ApiError extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: vi.fn() }) }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/components/ui/Sheet', () => ({
  default: ({ open, children }: { open: boolean; children: React.ReactNode }) => (open ? <div>{children}</div> : null),
}))

afterEach(() => { create.mockReset(); update.mockReset() })

const stored: LoreRead = {
  id: 4, title: 'La torre', body: 'Testo', tags: ['luoghi'], has_image: true, has_audio: false,
  revealed: false, revealed_at: null, created_at: '2026-11-01T09:00:00', updated_at: '2026-11-01T09:00:00',
}
const fileInput = () => document.querySelector('input[type=file][accept^="image"]') as HTMLInputElement

describe('LoreEditorSheet FormData', () => {
  it('crea: titolo, testo, tag JSON e immagine', async () => {
    create.mockResolvedValue(stored)
    renderWithProviders(<LoreEditorSheet open campaignId={1} lore={null} onClose={() => {}} />)
    await userEvent.type(screen.getAllByRole('textbox')[0], 'Nuova')
    await userEvent.type(screen.getAllByRole('textbox')[1], 'Corpo')
    const img = new File(['x'], 'a.png', { type: 'image/png' })
    await userEvent.upload(fileInput(), img)
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    await waitFor(() => expect(create).toHaveBeenCalled())
    const [cid, fd] = create.mock.calls[0] as [number, FormData]
    expect(cid).toBe(1)
    expect(fd.get('title')).toBe('Nuova')
    expect(fd.get('body')).toBe('Corpo')
    expect(fd.get('tags')).toBe('[]')
    expect((fd.get('image') as File).name).toBe('a.png')
    expect(fd.has('remove_image')).toBe(false)
  })

  it('modifica: Rimuovi su immagine salvata invia remove_image', async () => {
    update.mockResolvedValue(stored)
    renderWithProviders(<LoreEditorSheet open campaignId={1} lore={stored} onClose={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: 'campaign.lore.remove_file' }))
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    await waitFor(() => expect(update).toHaveBeenCalled())
    const [, id, fd] = update.mock.calls[0] as [number, number, FormData]
    expect(id).toBe(4)
    expect(fd.get('remove_image')).toBe('true')
    expect(fd.has('image')).toBe(false)
  })

  it('Rimuovi su un file appena scelto toglie solo la scelta, senza flag', async () => {
    update.mockResolvedValue(stored)
    renderWithProviders(<LoreEditorSheet open campaignId={1} lore={stored} onClose={() => {}} />)
    await userEvent.upload(fileInput(), new File(['x'], 'b.png', { type: 'image/png' }))
    await userEvent.click(screen.getByRole('button', { name: 'campaign.lore.remove_file' }))
    await userEvent.click(screen.getByRole('button', { name: 'common.save' }))
    await waitFor(() => expect(update).toHaveBeenCalled())
    const fd = update.mock.calls[0][2] as FormData
    expect(fd.has('image')).toBe(false)
    expect(fd.has('remove_image')).toBe(false)
  })
})

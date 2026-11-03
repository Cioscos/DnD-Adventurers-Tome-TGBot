import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import LoreSection from '@/pages/campaign/LoreSection'
import type { LoreRead } from '@/types'

const { list, reveal, hide, remove } = vi.hoisted(() => ({ list: vi.fn(), reveal: vi.fn(), hide: vi.fn(), remove: vi.fn() }))

vi.mock('@/api/client', () => ({
  api: {
    lore: {
      list, reveal, hide, remove, create: vi.fn(), update: vi.fn(),
      imageUrl: (c: number, i: number) => `/img/${c}/${i}`,
      audioUrl: (c: number, i: number) => `/aud/${c}/${i}`,
    },
  },
  ApiError: class ApiError extends Error { constructor(public status: number, public detail: unknown) { super('x') } },
}))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ info: vi.fn(), error: vi.fn(), success: vi.fn() }) }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/components/ui/Sheet', () => ({
  default: ({ open, children, title }: { open: boolean; children: React.ReactNode; title?: string }) =>
    open ? <div role="dialog" aria-label={title}>{children}</div> : null,
}))

afterEach(() => { list.mockReset(); reveal.mockReset(); hide.mockReset(); remove.mockReset() })

const mk = (o: Partial<LoreRead>): LoreRead => ({
  id: 1, title: 'La torre', body: 'Testo della torre', tags: ['luoghi'], has_image: false, has_audio: false,
  revealed: true, revealed_at: '2026-11-01T10:00:00', created_at: '2026-11-01T09:00:00', updated_at: '2026-11-01T09:00:00', ...o,
})
const entries = [
  mk({ id: 1 }),
  mk({ id: 2, title: 'Il segreto', tags: ['trama'], revealed: false, revealed_at: null, has_image: true, has_audio: true }),
]

describe('LoreSection', () => {
  it('master: bozza etichettata, azioni Rivela/Nascondi/Modifica/Elimina', async () => {
    list.mockResolvedValue(entries)
    renderWithProviders(<LoreSection campaignId={1} isGm />)
    await screen.findByText('Il segreto')
    expect(screen.getAllByText('campaign.lore.draft')).toHaveLength(1)
    expect(screen.getByRole('button', { name: 'campaign.lore.reveal' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'campaign.lore.hide' })).toBeTruthy()
    expect(screen.getAllByRole('button', { name: 'common.edit' })).toHaveLength(2)
    expect(screen.getAllByRole('button', { name: 'common.delete' })).toHaveLength(2)
  })

  it('master: Rivela chiama l API; Elimina chiede conferma in-app', async () => {
    list.mockResolvedValue(entries)
    reveal.mockResolvedValue(mk({ id: 2 }))
    remove.mockResolvedValue(undefined)
    const confirmSpy = vi.spyOn(window, 'confirm')
    renderWithProviders(<LoreSection campaignId={1} isGm />)
    await userEvent.click(await screen.findByRole('button', { name: 'campaign.lore.reveal' }))
    await waitFor(() => expect(reveal).toHaveBeenCalledWith(1, 2))
    await userEvent.click(screen.getAllByRole('button', { name: 'common.delete' })[0])
    expect(remove).not.toHaveBeenCalled()
    await userEvent.click(await screen.findByRole('button', { name: 'campaign.lore.delete_confirm' }))
    await waitFor(() => expect(remove).toHaveBeenCalledWith(1, 1))
    expect(confirmSpy).not.toHaveBeenCalled()
  })

  it('giocatore: solo rivelate, nessuna azione', async () => {
    list.mockResolvedValue([entries[0]])
    renderWithProviders(<LoreSection campaignId={1} isGm={false} />)
    await screen.findByText('La torre')
    expect(screen.queryByText('campaign.lore.draft')).toBeNull()
    expect(screen.queryByRole('button', { name: 'common.edit' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'common.delete' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'campaign.lore.reveal' })).toBeNull()
  })

  it('filtro tag', async () => {
    list.mockResolvedValue(entries)
    renderWithProviders(<LoreSection campaignId={1} isGm />)
    await screen.findByText('Il segreto')
    await userEvent.click(screen.getByRole('button', { name: /^trama$/ }))
    expect(screen.queryByText('La torre')).toBeNull()
    expect(screen.getByText('Il segreto')).toBeTruthy()
  })

  it('tocco su una voce apre la modale con testo, immagine e audio', async () => {
    list.mockResolvedValue(entries)
    renderWithProviders(<LoreSection campaignId={1} isGm />)
    await userEvent.click(await screen.findByText('Il segreto'))
    const dialog = await screen.findByRole('dialog', { name: 'Il segreto' })
    expect(dialog.querySelector('img')?.getAttribute('src')).toBe('/img/1/2')
    expect(dialog.querySelector('audio')?.getAttribute('src')).toBe('/aud/1/2')
  })
})

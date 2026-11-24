import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../utils/renderWithProviders'
import Maps from '@/pages/Maps'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))

vi.mock('@/api/client', () => ({ api: { characters: { get }, maps: { fileUrl: (c: number, m: number) => `/file/${c}/${m}` } } }))
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig<typeof import('react-router-dom')>()), useParams: () => ({ id: '7' }), useNavigate: () => () => {},
}))
vi.mock('react-i18next', async (orig) => ({
  ...(await orig<typeof import('react-i18next')>()), useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }),
}))
vi.mock('@/components/Layout', () => ({ default: (p: { children: unknown }) => p.children }))
vi.mock('@/pages/maps/MapZoneGroup', () => ({
  default: (p: { maps: unknown[]; onPreview: (m: unknown) => void }) => <button onClick={() => p.onPreview(p.maps[0])}>apri</button>,
}))

const mappa = (over: object) => ({
  id: 1, zone_name: 'Cripta', file_id: '', file_type: 'document', size_bytes: 1000, local_file_path: 'data/maps/7/a.pdf', ...over,
})

async function apri(over: object) {
  get.mockResolvedValue({ id: 7, name: 'P', maps: [mappa(over)] })
  renderWithProviders(<Maps />)
  await userEvent.click(await screen.findByText('apri'))
}

describe('caccia: mappe PDF', () => {
  // caccia: {"id": "CB-010", "fonte": "invariante: il PDF caricato ha un'anteprima, con il file sempre apribile", "zona": "flusso:note-mappe", "voce": "contratto", "copre": ["route:/char/:id/maps"]}
  it('un PDF caricato mostra l\'anteprima e il link al file', async () => {
    await apri({})
    expect(await screen.findByTitle('Cripta')).toHaveAttribute('src', '/file/7/1')
    expect(screen.getByText('character.maps.open_file')).toHaveAttribute('href', '/file/7/1')
  })

  // caccia: {"id": "CB-026", "fonte": "invariante: un documento non PDF resta apribile", "zona": "flusso:note-mappe", "voce": "limiti", "copre": ["route:/char/:id/maps"]}
  it('un documento da Telegram o un PDF grande ha solo il link', async () => {
    await apri({ local_file_path: null })
    expect(await screen.findByText('character.maps.open_file')).toBeInTheDocument()
    expect(screen.queryByTitle('Cripta')).toBeNull()
  })
})

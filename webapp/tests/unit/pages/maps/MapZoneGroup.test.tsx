import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import MapZoneGroup from '@/pages/maps/MapZoneGroup'
import type { MapEntry } from '@/types'

vi.mock('@/api/client', () => ({ api: { maps: { reorder: vi.fn(), fileUrl: (c: number, id: number) => `https://x/${c}/${id}` } } }))
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))

const maps = [
  { id: 1, zone_name: 'Foresta', file_type: 'photo', position: 0 },
  { id: 2, zone_name: 'Foresta', file_type: 'pdf', position: 1 },
] as MapEntry[]

const base = { charId: 7, zoneName: 'Foresta', onAddMore: () => {}, onDeleteFile: () => {}, onDeleteZone: () => {}, onPreview: () => {} }

describe('MapZoneGroup', () => {
  it('renders the zone name and map count', () => {
    renderWithProviders(<MapZoneGroup {...base} maps={maps} />)
    expect(screen.getByText('Foresta')).toBeInTheDocument()
    expect(screen.getByText('(2)')).toBeInTheDocument()
  })

  it('wires add-more and delete-zone', async () => {
    const onAddMore = vi.fn(); const onDeleteZone = vi.fn()
    renderWithProviders(<MapZoneGroup {...base} maps={maps} onAddMore={onAddMore} onDeleteZone={onDeleteZone} />)
    await userEvent.click(screen.getByText(/character.maps.add_more/))
    expect(onAddMore).toHaveBeenCalledWith('Foresta')
    await userEvent.click(screen.getByText('character.maps.delete_zone'))
    expect(onDeleteZone).toHaveBeenCalledWith('Foresta')
  })

  it('previews a map and deletes a single file', async () => {
    const onPreview = vi.fn(); const onDeleteFile = vi.fn()
    renderWithProviders(<MapZoneGroup {...base} maps={[maps[0]]} onPreview={onPreview} onDeleteFile={onDeleteFile} />)
    await userEvent.click(screen.getByRole('button', { name: 'Foresta' }))
    expect(onPreview).toHaveBeenCalledWith(maps[0])
    await userEvent.click(screen.getByRole('button', { name: 'common.delete' }))
    expect(onDeleteFile).toHaveBeenCalledWith(1, 'Foresta')
  })
})

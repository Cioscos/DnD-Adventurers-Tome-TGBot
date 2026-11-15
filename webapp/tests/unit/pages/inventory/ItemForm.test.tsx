import { describe, it, expect, vi } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { renderWithProviders } from '../../utils/renderWithProviders'
import ItemForm from '@/pages/inventory/ItemForm'
import type { Item } from '@/types'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))

const box = {
  id: 1, name: 'Zaino', item_type: 'gear', quantity: 1, weight: 5, is_equipped: false, container_id: null,
  item_metadata: { container: { capacity_lb: 30, counts_weight: true, quick_access: false, coins: { gold: 12 } } },
} as unknown as Item

describe('ItemForm contenitore', () => {
  it('spegnere e riaccendere "È un contenitore" non perde capienza né monete', () => {
    const onSubmit = vi.fn()
    renderWithProviders(<ItemForm initialData={box} onSubmit={onSubmit} onCancel={vi.fn()} isPending={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'common.next' }))
    const sw = screen.getByLabelText('character.inventory.containers.is_container')
    fireEvent.click(sw)
    fireEvent.click(screen.getByLabelText('character.inventory.containers.is_container'))
    fireEvent.click(screen.getByRole('button', { name: 'common.next' }))
    fireEvent.click(screen.getByRole('button', { name: 'common.save' }))
    expect(onSubmit.mock.calls[0][0].extra_meta.container).toMatchObject({ capacity_lb: 30, coins: { gold: 12 } })
  })
})

describe('ItemForm catalogo per edizione', () => {
  const open = async (edition: string) => {
    renderWithProviders(<ItemForm edition={edition} onSubmit={vi.fn()} onCancel={vi.fn()} isPending={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'character.inventory.from_equipment' }))
    await screen.findByText('Ascia da battaglia')
  }

  it('un 2024 carica equipment-2024 (c’è il Moschetto)', async () => {
    await open('2024')
    expect(screen.getByText('Moschetto')).toBeTruthy()
  })

  it('un 2014 resta sul catalogo equipment', async () => {
    await open('2014')
    expect(screen.queryByText('Moschetto')).toBeNull()
  })
})

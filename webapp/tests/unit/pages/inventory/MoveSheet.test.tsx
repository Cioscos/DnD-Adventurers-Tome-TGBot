import { describe, it, expect, vi } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { renderWithProviders } from '../../utils/renderWithProviders'
import MoveSheet from '@/pages/inventory/MoveSheet'
import type { Item } from '@/types'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))

const box = (id: number, name: string, parent: number | null, cap: number | null, weight: number): Item => ({
  id, name, item_type: 'gear', quantity: 1, weight, is_equipped: false, container_id: parent,
  item_metadata: { container: { capacity_lb: cap, counts_weight: true, quick_access: false, coins: {} } },
  container_stats: { contents_weight: weight, items_count: 0, containers_count: 0, over_capacity: false },
} as unknown as Item)
const thing = (id: number, name: string, qty = 1, w = 1): Item =>
  ({ id, name, item_type: 'gear', quantity: qty, weight: w, is_equipped: false, container_id: null }) as unknown as Item

const zaino = box(1, 'Zaino', null, 30, 5)
const tasca = box(2, 'Tasca', 1, 5, 1)
const borsa = box(3, 'Borsa', null, 6, 0)

function setup(moving: Item[], items: Item[], currentId: number | null = null) {
  const onMove = vi.fn()
  renderWithProviders(
    <MoveSheet items={items} moving={moving} currentId={currentId} onMove={onMove}
      onNewContainer={vi.fn()} onClose={vi.fn()} />,
  )
  return onMove
}

describe('MoveSheet', () => {
  it('disabilita il contenitore corrente', () => {
    const w = thing(9, 'Corda')
    setup([w], [zaino, tasca, borsa, w], 1)
    expect(screen.getByRole('button', { name: /Zaino/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: /Borsa/ })).toBeEnabled()
  })

  it('disabilita sé stesso e i discendenti per un contenitore spostato', () => {
    setup([zaino], [zaino, tasca, borsa])
    expect(screen.getByRole('button', { name: /Zaino/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: /Tasca/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: /Borsa/ })).toBeEnabled()
  })

  it('mostra l\'avviso oltre la capacità', () => {
    const heavy = thing(9, 'Incudine', 1, 10)
    setup([heavy], [zaino, borsa, heavy])
    expect(screen.getByRole('button', { name: /Borsa/ }).textContent).toContain('⚠')
    expect(screen.getByRole('button', { name: /Zaino/ }).textContent).not.toContain('⚠')
  })

  it('con un oggetto x10 mostra lo stepper e passa la quantità', () => {
    const frecce = thing(9, 'Frecce', 10, 0.1)
    const onMove = setup([frecce], [zaino, frecce])
    fireEvent.click(screen.getByLabelText('character.inventory.containers.qty_minus'))
    fireEvent.click(screen.getByRole('button', { name: /Zaino/ }))
    expect(onMove).toHaveBeenCalledWith(1, 9)
  })

  it('spostando tutta la pila non invia la quantità', () => {
    const frecce = thing(9, 'Frecce', 20, 0.1)
    const onMove = setup([frecce], [zaino, frecce])
    fireEvent.click(screen.getByRole('button', { name: /Zaino/ }))
    expect(onMove).toHaveBeenCalledWith(1, undefined)
  })

  it('senza quantità multipla non mostra lo stepper', () => {
    setup([thing(9, 'Corda')], [zaino])
    expect(screen.queryByLabelText('character.inventory.containers.qty_minus')).toBeNull()
  })
})

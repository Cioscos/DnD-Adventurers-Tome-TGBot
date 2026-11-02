import { describe, it, expect, vi } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { renderWithProviders } from '../../utils/renderWithProviders'
import ContainerForm from '@/pages/inventory/ContainerForm'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))

describe('ContainerForm', () => {
  it('preset Faretra: senza capacità e a portata di mano', () => {
    const onSubmit = vi.fn()
    renderWithProviders(<ContainerForm onSubmit={onSubmit} onCancel={vi.fn()} isPending={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'character.inventory.containers.presets.quiver' }))
    fireEvent.click(screen.getByRole('button', { name: 'common.add' }))
    const arg = onSubmit.mock.calls[0][0]
    expect(arg.weight).toBe(1)
    expect(arg.container).toMatchObject({ capacity_lb: null, quick_access: true, counts_weight: true })
  })

  it('preset Zaino: 30 lb, peso 5, nome di default', () => {
    const onSubmit = vi.fn()
    renderWithProviders(<ContainerForm onSubmit={onSubmit} onCancel={vi.fn()} isPending={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'character.inventory.containers.presets.backpack' }))
    fireEvent.click(screen.getByRole('button', { name: 'common.add' }))
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      name: 'character.inventory.containers.presets.backpack', weight: 5,
      container: { capacity_lb: 30, quick_access: false },
    })
  })
})

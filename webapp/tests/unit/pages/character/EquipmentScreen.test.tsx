import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../utils/renderWithProviders'
import EquipmentScreen from '@/pages/character/EquipmentScreen'
import type { CharacterFull } from '@/types'

vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return { ...actual, useTranslation: () => ({ t: (k: string) => k, i18n: { language: 'it' } }) }
})
vi.mock('@/api/client', () => ({
  api: { silhouette: { upload: vi.fn(), remove: vi.fn(), fileUrl: (id: number) => `file://sil/${id}` } },
}))
vi.mock('@/lib/silhouette', () => ({ silhouetteUrl: () => 'sil://default' }))
vi.mock('@/hooks/useToast', () => ({ useToast: () => ({ error: vi.fn(), success: vi.fn() }) }))
vi.mock('@/auth/telegram', () => ({ haptic: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/components/ui/SectionDivider', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { open: boolean; children?: unknown }) => (p.open ? React.createElement('div', { 'data-testid': 'sheet' }, p.children) : null) }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return { default: (p: { onClick?: () => void; children?: unknown }) => React.createElement('button', { onClick: p.onClick }, p.children) }
})
vi.mock('@/components/character/EquipmentStatsFooter', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'stats-footer' }) }
})
vi.mock('@/components/character/PaperDoll', async () => {
  const React = await import('react')
  return {
    default: (p: { silhouetteUrl?: string | null; onSlotTap: (s: string, i: unknown) => void; silhouetteAction?: unknown }) =>
      React.createElement(
        'div',
        { 'data-testid': 'paper-doll', 'data-sil': p.silhouetteUrl ?? '' },
        React.createElement('button', { 'data-testid': 'tap-empty', onClick: () => p.onSlotTap('head', null) }, 'empty'),
        React.createElement('button', { 'data-testid': 'tap-equipped', onClick: () => p.onSlotTap('body', { id: 9, name: 'Plate' }) }, 'equipped'),
        p.silhouetteAction,
      ),
  }
})
vi.mock('@/components/character/EquipItemPicker', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'picker' }) }
})
vi.mock('@/components/character/SlotActionSheet', async () => {
  const React = await import('react')
  return {
    default: (p: { onReplace: () => void; onDetails: (i: unknown) => void }) =>
      React.createElement(
        'div',
        { 'data-testid': 'actions' },
        React.createElement('button', { 'data-testid': 'sa-replace', onClick: p.onReplace }, 'replace'),
        React.createElement('button', { 'data-testid': 'sa-details', onClick: () => p.onDetails({ id: 9, name: 'Plate' }) }, 'details'),
      ),
  }
})
vi.mock('@/components/character/ItemDetailsModal', async () => {
  const React = await import('react')
  return { default: () => React.createElement('div', { 'data-testid': 'details' }) }
})

const char = (over: Partial<CharacterFull> = {}): CharacterFull =>
  ({ id: 42, items: [], has_custom_silhouette: false, ...over } as unknown as CharacterFull)

describe('EquipmentScreen', () => {
  it('renders the paper-doll and the stats footer', () => {
    renderWithProviders(<EquipmentScreen char={char()} />)
    expect(screen.getByTestId('paper-doll')).toBeInTheDocument()
    expect(screen.getByTestId('stats-footer')).toBeInTheDocument()
  })

  it('tapping an empty slot opens the equip picker', async () => {
    renderWithProviders(<EquipmentScreen char={char()} />)
    expect(screen.queryByTestId('picker')).not.toBeInTheDocument()
    await userEvent.click(screen.getByTestId('tap-empty'))
    expect(screen.getByTestId('picker')).toBeInTheDocument()
  })

  it('tapping an equipped slot opens the action sheet, whose replace switches to the picker', async () => {
    renderWithProviders(<EquipmentScreen char={char()} />)
    await userEvent.click(screen.getByTestId('tap-equipped'))
    expect(screen.getByTestId('actions')).toBeInTheDocument()
    await userEvent.click(screen.getByTestId('sa-replace'))
    expect(screen.getByTestId('picker')).toBeInTheDocument()
  })

  it('the action sheet "details" opens the item details modal', async () => {
    renderWithProviders(<EquipmentScreen char={char()} />)
    await userEvent.click(screen.getByTestId('tap-equipped'))
    await userEvent.click(screen.getByTestId('sa-details'))
    expect(screen.getByTestId('details')).toBeInTheDocument()
  })

  it('uses the custom silhouette file URL when the character has one', () => {
    renderWithProviders(<EquipmentScreen char={char({ has_custom_silhouette: true })} />)
    expect(screen.getByTestId('paper-doll')).toHaveAttribute('data-sil', 'file://sil/42')
  })

  it('falls back to the manifest silhouette URL when there is no custom one', () => {
    renderWithProviders(<EquipmentScreen char={char({ has_custom_silhouette: false })} />)
    expect(screen.getByTestId('paper-doll')).toHaveAttribute('data-sil', 'sil://default')
  })
})

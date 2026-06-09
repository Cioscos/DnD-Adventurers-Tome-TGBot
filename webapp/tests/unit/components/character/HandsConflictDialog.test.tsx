import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import HandsConflictDialog from '@/components/character/HandsConflictDialog'
import type { Item } from '@/types'

// t echoes the interpolated item names so the conflict body can be asserted.
vi.mock('react-i18next', async (orig) => {
  const actual = (await orig()) as Record<string, unknown>
  return {
    ...actual,
    useTranslation: () => ({
      t: (k: string, opts?: { newItem?: string; removedItem?: string }) =>
        opts && (opts.newItem || opts.removedItem) ? `${opts.newItem} / ${opts.removedItem}` : k,
      i18n: { language: 'it' },
    }),
  }
})
vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', { 'data-testid': 'sheet' }, p.children) }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return {
    default: (p: { onClick?: () => void; disabled?: boolean; loading?: boolean; children?: unknown }) =>
      React.createElement('button', { onClick: p.onClick, disabled: p.disabled || p.loading }, p.children),
  }
})

const sword = { id: 1, name: 'Greatsword' } as Item
const shield = { id: 2, name: 'Shield' } as Item

describe('HandsConflictDialog', () => {
  it('explains which item replaces which', () => {
    render(<HandsConflictDialog newItem={sword} removedItem={shield} onConfirm={() => {}} onCancel={() => {}} />)
    expect(screen.getByText('Greatsword / Shield')).toBeInTheDocument()
  })

  it('cancel and confirm trigger their callbacks (confirm is the rightmost button)', async () => {
    const onConfirm = vi.fn()
    const onCancel = vi.fn()
    render(<HandsConflictDialog newItem={sword} removedItem={shield} onConfirm={onConfirm} onCancel={onCancel} />)
    const buttons = screen.getAllByRole('button')
    expect(buttons[buttons.length - 1]).toHaveTextContent('character.equipment.hands_conflict.confirm')
    await userEvent.click(screen.getByRole('button', { name: 'common.cancel' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('button', { name: 'character.equipment.hands_conflict.confirm' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('disables the confirm button while the swap is pending', () => {
    render(<HandsConflictDialog newItem={sword} removedItem={shield} pending onConfirm={() => {}} onCancel={() => {}} />)
    expect(screen.getByRole('button', { name: 'character.equipment.hands_conflict.confirm' })).toBeDisabled()
  })
})

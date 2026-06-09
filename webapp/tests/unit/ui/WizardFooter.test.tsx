import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import WizardFooter from '@/components/ui/WizardFooter'

vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return {
    default: (p: { onClick?: () => void; disabled?: boolean; loading?: boolean; children?: unknown }) =>
      React.createElement('button', { onClick: p.onClick, disabled: p.disabled || p.loading }, p.children),
  }
})

describe('WizardFooter', () => {
  it('renders the secondary (left) and primary (right) actions', () => {
    render(<WizardFooter secondaryLabel="Indietro" onSecondary={() => {}} primaryLabel="Avanti" onPrimary={() => {}} />)
    const buttons = screen.getAllByRole('button')
    expect(buttons[0]).toHaveTextContent('Indietro')
    expect(buttons[buttons.length - 1]).toHaveTextContent('Avanti')
  })

  it('fires the secondary and primary callbacks', async () => {
    const onSecondary = vi.fn()
    const onPrimary = vi.fn()
    render(<WizardFooter secondaryLabel="Annulla" onSecondary={onSecondary} primaryLabel="Crea" onPrimary={onPrimary} />)
    await userEvent.click(screen.getByRole('button', { name: 'Annulla' }))
    expect(onSecondary).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('button', { name: 'Crea' }))
    expect(onPrimary).toHaveBeenCalledTimes(1)
  })

  it('disables the primary action when disabled or loading', () => {
    const { rerender } = render(<WizardFooter secondaryLabel="X" onSecondary={() => {}} primaryLabel="Salva" onPrimary={() => {}} primaryDisabled />)
    expect(screen.getByRole('button', { name: 'Salva' })).toBeDisabled()
    rerender(<WizardFooter secondaryLabel="X" onSecondary={() => {}} primaryLabel="Salva" onPrimary={() => {}} primaryLoading />)
    expect(screen.getByRole('button', { name: 'Salva' })).toBeDisabled()
  })
})

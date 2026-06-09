import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ConfirmSheet from '@/components/ui/ConfirmSheet'

vi.mock('@/components/ui/Sheet', async () => {
  const React = await import('react')
  return {
    default: (p: { open: boolean; title?: unknown; children?: unknown }) =>
      p.open ? React.createElement('div', null, React.createElement('h2', null, p.title), p.children) : null,
  }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return {
    default: (p: { onClick?: () => void; disabled?: boolean; loading?: boolean; children?: unknown }) =>
      React.createElement('button', { onClick: p.onClick, disabled: p.disabled || p.loading }, p.children),
  }
})

describe('ConfirmSheet', () => {
  it('renders title, body and both actions when open', () => {
    render(<ConfirmSheet open onClose={() => {}} onConfirm={() => {}} title="Eliminare?" body="Azione irreversibile" confirmLabel="Elimina" cancelLabel="Annulla" />)
    expect(screen.getByText('Eliminare?')).toBeInTheDocument()
    expect(screen.getByText('Azione irreversibile')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Elimina' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Annulla' })).toBeInTheDocument()
  })

  it('wires cancel→onClose and confirm→onConfirm, with confirm as the rightmost button', async () => {
    const onClose = vi.fn()
    const onConfirm = vi.fn()
    render(<ConfirmSheet open onClose={onClose} onConfirm={onConfirm} title="T" confirmLabel="OK" cancelLabel="No" />)
    const buttons = screen.getAllByRole('button')
    expect(buttons[buttons.length - 1]).toHaveTextContent('OK')
    await userEvent.click(screen.getByRole('button', { name: 'No' }))
    expect(onClose).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('button', { name: 'OK' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('disables the confirm button while loading', () => {
    render(<ConfirmSheet open onClose={() => {}} onConfirm={() => {}} title="T" confirmLabel="OK" loading />)
    expect(screen.getByRole('button', { name: 'OK' })).toBeDisabled()
  })
})

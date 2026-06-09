import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import EmptyState from '@/components/ui/EmptyState'

vi.mock('@/components/ui/Surface', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', null, p.children) }
})
vi.mock('@/components/ui/Button', async () => {
  const React = await import('react')
  return {
    default: (p: { onClick?: () => void; children?: unknown }) => React.createElement('button', { onClick: p.onClick }, p.children),
  }
})

describe('EmptyState', () => {
  it('renders the title and optional hint', () => {
    render(<EmptyState title="Nessun oggetto" hint="Aggiungine uno" />)
    expect(screen.getByText('Nessun oggetto')).toBeInTheDocument()
    expect(screen.getByText('Aggiungine uno')).toBeInTheDocument()
  })

  it('renders no CTA button when no action is given', () => {
    render(<EmptyState title="Vuoto" />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('renders the action CTA and fires its onClick', async () => {
    const onClick = vi.fn()
    render(<EmptyState title="Vuoto" action={{ label: 'Aggiungi', onClick }} />)
    await userEvent.click(screen.getByRole('button', { name: 'Aggiungi' }))
    expect(onClick).toHaveBeenCalledTimes(1)
  })
})

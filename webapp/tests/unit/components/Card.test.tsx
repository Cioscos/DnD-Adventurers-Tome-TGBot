import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Card from '@/components/Card'

vi.mock('@/components/ui/Surface', async () => {
  const React = await import('react')
  return {
    default: (p: { variant?: string; onClick?: () => void; children?: unknown }) =>
      React.createElement('div', { 'data-variant': p.variant, onClick: p.onClick }, p.children),
  }
})

describe('Card', () => {
  it('maps the default variant to Surface "flat"', () => {
    const { container } = render(<Card>contenuto</Card>)
    expect(screen.getByText('contenuto')).toBeInTheDocument()
    expect(container.firstChild).toHaveAttribute('data-variant', 'flat')
  })

  it('maps the elevated variant to Surface "elevated"', () => {
    const { container } = render(<Card variant="elevated">x</Card>)
    expect(container.firstChild).toHaveAttribute('data-variant', 'elevated')
  })

  it('forwards onClick', async () => {
    const onClick = vi.fn()
    render(<Card onClick={onClick}>x</Card>)
    await userEvent.click(screen.getByText('x'))
    expect(onClick).toHaveBeenCalledTimes(1)
  })
})

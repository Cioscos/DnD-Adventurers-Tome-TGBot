import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import Toast from '@/components/ui/Toast'

vi.mock('sonner', async () => {
  const React = await import('react')
  return { Toaster: () => React.createElement('div', { 'data-testid': 'sonner-toaster' }) }
})

describe('Toast', () => {
  it('mounts the sonner toaster (portaled to body)', () => {
    render(<Toast />)
    expect(screen.getByTestId('sonner-toaster')).toBeInTheDocument()
  })
})

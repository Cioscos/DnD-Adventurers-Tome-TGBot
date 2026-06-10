import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import AppErrorBoundary from '@/components/AppErrorBoundary'

function Bomb(): never {
  throw new Error('boom')
}

describe('AppErrorBoundary', () => {
  beforeEach(() => {
    // React logga gli errori catturati dai boundary: silenziali nel test
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders children when nothing throws', () => {
    render(
      <AppErrorBoundary>
        <p>contenuto ok</p>
      </AppErrorBoundary>,
    )
    expect(screen.getByText('contenuto ok')).toBeInTheDocument()
  })

  it('shows the fallback with a reload button when a child throws in render', () => {
    render(
      <AppErrorBoundary>
        <Bomb />
      </AppErrorBoundary>,
    )
    expect(screen.getByText('Qualcosa è andato storto')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ricarica' })).toBeInTheDocument()
  })
})

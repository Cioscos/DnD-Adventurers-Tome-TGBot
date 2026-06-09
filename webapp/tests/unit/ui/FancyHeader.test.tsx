import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import FancyHeader from '@/components/ui/FancyHeader'

vi.mock('@/components/ui/Ornament', async () => {
  const React = await import('react')
  return { FlourishDivider: () => React.createElement('div', { 'data-testid': 'flourish' }) }
})

describe('FancyHeader', () => {
  it('renders the title as a level-1 heading', () => {
    render(<FancyHeader title="La Tana del Drago" />)
    expect(screen.getByRole('heading', { level: 1, name: 'La Tana del Drago' })).toBeInTheDocument()
  })

  it('renders an optional subtitle', () => {
    render(<FancyHeader title="T" subtitle="sottotitolo" />)
    expect(screen.getByText('sottotitolo')).toBeInTheDocument()
  })

  it('flanks a centered header with flourishes, none when left-aligned', () => {
    const { rerender } = render(<FancyHeader title="T" align="center" />)
    expect(screen.getAllByTestId('flourish')).toHaveLength(2)
    rerender(<FancyHeader title="T" align="left" />)
    expect(screen.queryByTestId('flourish')).not.toBeInTheDocument()
  })
})

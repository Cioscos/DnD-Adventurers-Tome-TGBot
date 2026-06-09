import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import SectionDivider from '@/components/ui/SectionDivider'

vi.mock('@/components/ui/Ornament', async () => {
  const React = await import('react')
  return { FlourishDivider: () => React.createElement('div', { 'data-testid': 'flourish' }) }
})

describe('SectionDivider', () => {
  it('renders its children', () => {
    render(<SectionDivider>Sezione</SectionDivider>)
    expect(screen.getByText('Sezione')).toBeInTheDocument()
  })

  it('left alignment renders a single flourish', () => {
    render(<SectionDivider align="left">A</SectionDivider>)
    expect(screen.getAllByTestId('flourish')).toHaveLength(1)
  })

  it('center alignment renders flanking flourishes', () => {
    render(<SectionDivider align="center">A</SectionDivider>)
    expect(screen.getAllByTestId('flourish')).toHaveLength(2)
  })
})

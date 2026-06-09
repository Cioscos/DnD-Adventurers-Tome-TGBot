import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import SectionHeader from '@/components/SectionHeader'

vi.mock('@/components/ui/SectionDivider', async () => {
  const React = await import('react')
  return { default: (p: { children?: unknown }) => React.createElement('div', { 'data-testid': 'divider' }, p.children) }
})

describe('SectionHeader', () => {
  it('renders its children through a SectionDivider', () => {
    render(<SectionHeader>Combattimento</SectionHeader>)
    expect(screen.getByTestId('divider')).toHaveTextContent('Combattimento')
  })
})

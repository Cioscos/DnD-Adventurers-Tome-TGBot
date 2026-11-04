import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import SectionDivider from '@/components/ui/SectionDivider'

describe('SectionDivider', () => {
  it('renders its children as a section title', () => {
    render(<SectionDivider>Sezione</SectionDivider>)
    expect(screen.getByRole('heading', { name: 'Sezione' })).toBeInTheDocument()
  })

  it('center alignment centers the title', () => {
    render(<SectionDivider align="center">A</SectionDivider>)
    expect(screen.getByRole('heading', { name: 'A' }).className).toContain('justify-center')
  })
})

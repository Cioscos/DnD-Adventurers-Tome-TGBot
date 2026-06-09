import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import DiceIcon from '@/components/ui/DiceIcon'

describe('DiceIcon', () => {
  it('labels each polyhedral die with its number of sides', () => {
    const { rerender } = render(<DiceIcon sides={20} />)
    expect(screen.getByText('20')).toBeInTheDocument()
    rerender(<DiceIcon sides={6} />)
    expect(screen.getByText('6')).toBeInTheDocument()
    rerender(<DiceIcon sides={12} />)
    expect(screen.getByText('12')).toBeInTheDocument()
  })

  it('renders a percentile (%) glyph for the d100', () => {
    render(<DiceIcon sides={100} />)
    expect(screen.getByText('%')).toBeInTheDocument()
  })
})

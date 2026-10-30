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

  // Il viewBox è 60 unità: i px reali sono fontSize × size / 60. Le taglie sono
  // quelle dei punti d'uso (Dadi 42 e 34, Statistiche, overlay e Tiri Salvezza 28).
  it.each([28, 34, 42, 48])('draws the numeral at 12 px or more when rendered at %i px', (size) => {
    for (const sides of [4, 6, 8, 10, 12, 20, 100] as const) {
      const { container, unmount } = render(<DiceIcon sides={sides} size={size} />)
      const fontSize = Number(container.querySelector('text')?.getAttribute('font-size'))
      expect(fontSize * size / 60).toBeGreaterThanOrEqual(12)
      unmount()
    }
  })
})

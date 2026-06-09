import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { CornerFlourish, CornerFlourishes, FlourishDivider } from '@/components/ui/Ornament'

describe('Ornament', () => {
  it('CornerFlourish renders a single SVG', () => {
    const { container } = render(<CornerFlourish />)
    expect(container.querySelectorAll('svg')).toHaveLength(1)
  })

  it('CornerFlourishes renders one flourish per corner (4)', () => {
    const { container } = render(<CornerFlourishes />)
    expect(container.querySelectorAll('svg')).toHaveLength(4)
  })

  it('FlourishDivider renders an SVG divider', () => {
    const { container } = render(<FlourishDivider />)
    expect(container.querySelector('svg')).not.toBeNull()
  })
})

import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { FlagIT, FlagEN } from '@/components/ui/Flags'

describe('Flags', () => {
  it('renders the Italian flag as an inline SVG', () => {
    const { container } = render(<FlagIT />)
    expect(container.querySelector('svg')).not.toBeNull()
  })

  it('renders the English flag as an inline SVG', () => {
    const { container } = render(<FlagEN />)
    expect(container.querySelector('svg')).not.toBeNull()
  })

  it('honors the size prop', () => {
    const { container } = render(<FlagIT size={28} />)
    expect(container.querySelector('svg')).toHaveAttribute('width', '28')
  })
})

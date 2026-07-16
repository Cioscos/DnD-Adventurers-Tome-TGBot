import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import Spinner from '@/components/ui/Spinner'

describe('Spinner', () => {
  it('renders a status element with animate-spin and the requested size', () => {
    const { getByRole } = render(<Spinner size={24} />)
    const el = getByRole('status')
    expect(el).toHaveClass('animate-spin')
    expect(el).toHaveStyle({ width: '24px', height: '24px' })
  })

  it('defaults to 16px', () => {
    const { getByRole } = render(<Spinner />)
    expect(getByRole('status')).toHaveStyle({ width: '16px', height: '16px' })
  })
})

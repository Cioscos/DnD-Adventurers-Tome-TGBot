import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import Skeleton from '@/components/ui/Skeleton'

describe('Skeleton', () => {
  it('Line/Circle/Rect render animated placeholder boxes', () => {
    const { container } = render(
      <div>
        <Skeleton.Line />
        <Skeleton.Circle />
        <Skeleton.Rect />
      </div>,
    )
    expect(container.querySelectorAll('.animate-skeleton').length).toBeGreaterThanOrEqual(3)
  })

  it('Group renders its children', () => {
    render(
      <Skeleton.Group>
        <Skeleton.Line className="child-a" />
        <Skeleton.Line className="child-b" />
      </Skeleton.Group>,
    )
    expect(document.querySelector('.child-a')).not.toBeNull()
    expect(document.querySelector('.child-b')).not.toBeNull()
  })
})

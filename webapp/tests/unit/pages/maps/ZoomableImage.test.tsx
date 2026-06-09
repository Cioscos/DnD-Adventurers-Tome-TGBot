import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import ZoomableImage from '@/pages/maps/ZoomableImage'

vi.mock('react-zoom-pan-pinch', async () => {
  const React = await import('react')
  return {
    TransformWrapper: (p: { children?: unknown }) => React.createElement('div', null, p.children),
    TransformComponent: (p: { children?: unknown }) => React.createElement('div', null, p.children),
  }
})

describe('ZoomableImage', () => {
  it('renders the image with its src and alt', () => {
    render(<ZoomableImage src="https://x/map.png" alt="Mappa" />)
    const img = screen.getByRole('img', { name: 'Mappa' })
    expect(img).toHaveAttribute('src', 'https://x/map.png')
  })
})

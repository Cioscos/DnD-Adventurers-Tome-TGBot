import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import ExpandChevron from '@/components/ui/ExpandChevron'

describe('ExpandChevron', () => {
  it('renders a decorative chevron hidden from the a11y tree', () => {
    const { container } = render(<ExpandChevron open={false} />)
    const wrapper = container.querySelector('span[aria-hidden]')
    expect(wrapper).not.toBeNull()
    expect(wrapper!.querySelector('svg')).not.toBeNull()
    expect(wrapper!.className).toContain('text-dnd-text-faint')
  })

  it('applies custom size and className', () => {
    const { container } = render(<ExpandChevron open size={20} className="text-dnd-gold-dim" />)
    const wrapper = container.querySelector('span[aria-hidden]')!
    expect(wrapper.className).toContain('text-dnd-gold-dim')
    expect(wrapper.className).toContain('shrink-0')
    expect(wrapper.querySelector('svg')!.getAttribute('width')).toBe('20')
  })
})

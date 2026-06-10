import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Sheet from '@/components/ui/Sheet'

vi.mock('@/styles/motion', () => ({ spring: new Proxy({}, { get: () => ({}) }) }))
vi.mock('@/store/overlayStore', () => ({ useRegisterOverlay: () => {} }))
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'drag', 'dragConstraints', 'dragElastic', 'dragControls', 'dragListener', 'onDragEnd', 'layout'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return {
    m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }),
    AnimatePresence: (p: { children?: unknown }) => React.createElement(React.Fragment, null, p.children),
    useDragControls: () => ({ start: () => {} }),
  }
})

describe('Sheet', () => {
  it('renders nothing when closed', () => {
    render(<Sheet open={false} onClose={() => {}}>body</Sheet>)
    expect(screen.queryByText('body')).not.toBeInTheDocument()
  })

  it('renders the title, children and a close button when open', () => {
    render(<Sheet open onClose={() => {}} title="Titolo">contenuto</Sheet>)
    expect(screen.getByText('Titolo')).toBeInTheDocument()
    expect(screen.getByText('contenuto')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument()
  })

  it('closes via the close button and the backdrop', async () => {
    const onClose = vi.fn()
    render(<Sheet open onClose={onClose} title="T">x</Sheet>)
    await userEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(onClose).toHaveBeenCalledTimes(1)
    fireEvent.click(document.querySelector('.fixed.inset-0') as HTMLElement)
    expect(onClose).toHaveBeenCalledTimes(2)
  })

  it('closes on Escape when dismissible', () => {
    const onClose = vi.fn()
    render(<Sheet open onClose={onClose}>x</Sheet>)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('hides the close button when not dismissible', () => {
    render(<Sheet open onClose={() => {}} title="T" dismissible={false}>x</Sheet>)
    expect(screen.queryByRole('button', { name: 'Close' })).not.toBeInTheDocument()
  })

  it('Escape only closes the topmost sheet when nested', () => {
    const onCloseOuter = vi.fn()
    const onCloseInner = vi.fn()
    render(
      <>
        <Sheet open onClose={onCloseOuter} title="Outer">x</Sheet>
        <Sheet open onClose={onCloseInner} title="Inner" zClassName="z-[60]">y</Sheet>
      </>,
    )
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onCloseInner).toHaveBeenCalledTimes(1)
    expect(onCloseOuter).not.toHaveBeenCalled()
  })

  it('applies the zClassName override to the backdrop wrapper', () => {
    render(<Sheet open onClose={() => {}} zClassName="z-[60]">x</Sheet>)
    expect(document.querySelector('.fixed.inset-0')).toHaveClass('z-[60]')
  })
})

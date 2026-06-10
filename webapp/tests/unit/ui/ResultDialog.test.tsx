import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ResultDialog from '@/components/ui/ResultDialog'

vi.mock('@/styles/motion', () => ({ spring: new Proxy({}, { get: () => ({}) }) }))
vi.mock('@/store/overlayStore', () => ({ useRegisterOverlay: () => {} }))
vi.mock('@/components/ui/Ornament', async () => {
  const React = await import('react')
  return { CornerFlourishes: () => React.createElement('span', { 'data-testid': 'flourishes' }) }
})
vi.mock('framer-motion', async () => {
  const React = await import('react')
  const MOTION = new Set(['initial', 'animate', 'exit', 'transition', 'variants', 'whileTap', 'whileHover', 'drag', 'layout'])
  const make = (tag: string) => (props: Record<string, unknown>) => {
    const clean: Record<string, unknown> = {}
    for (const k in props) if (!MOTION.has(k)) clean[k] = props[k]
    return React.createElement(tag, clean)
  }
  return {
    m: new Proxy({}, { get: (_t: object, tag: string | symbol) => make(String(tag)) }),
    AnimatePresence: (p: { children?: unknown }) => React.createElement(React.Fragment, null, p.children),
  }
})

describe('ResultDialog', () => {
  it('renders nothing when closed', () => {
    render(<ResultDialog open={false} onClose={() => {}}>body</ResultDialog>)
    expect(screen.queryByText('body')).not.toBeInTheDocument()
  })

  it('renders title, children and the default OK button when open', () => {
    render(<ResultDialog open onClose={() => {}} title="Esito">corpo</ResultDialog>)
    expect(screen.getByText('Esito')).toBeInTheDocument()
    expect(screen.getByText('corpo')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'OK' })).toBeInTheDocument()
  })

  it('closes via the OK button and via the backdrop', async () => {
    const onClose = vi.fn()
    render(<ResultDialog open onClose={onClose}>x</ResultDialog>)
    await userEvent.click(screen.getByRole('button', { name: 'OK' }))
    expect(onClose).toHaveBeenCalledTimes(1)
    fireEvent.click(document.querySelector('.fixed.inset-0') as HTMLElement)
    expect(onClose).toHaveBeenCalledTimes(2)
  })

  it('applies the accent border and the pulse class', () => {
    render(<ResultDialog open onClose={() => {}} accent="gold" pulse>x</ResultDialog>)
    // Il dialog è in portal su document.body, non nel container di render.
    const dialog = document.body.querySelector('.border-2') as HTMLElement
    expect(dialog.className).toContain('border-dnd-gold')
    expect(dialog.className).toContain('animate-pulse-gold')
  })

  it('hides the OK button when hideOkButton is set', () => {
    render(<ResultDialog open onClose={() => {}} hideOkButton>x</ResultDialog>)
    expect(screen.queryByRole('button', { name: 'OK' })).not.toBeInTheDocument()
  })
})

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ModalProvider from '@/components/ModalProvider'
import { useModal } from '@/components/modalContext'

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

function Consumer() {
  const { openModal, closeModal, isModalOpen } = useModal()
  return (
    <div>
      <button onClick={() => openModal({ content: <div>CORPO_MODALE</div> })}>apri</button>
      <button onClick={closeModal}>chiudi</button>
      <span data-testid="state">{isModalOpen ? 'aperto' : 'chiuso'}</span>
    </div>
  )
}

describe('ModalProvider', () => {
  it('provides openModal/closeModal and tracks isModalOpen across the stack', async () => {
    render(<ModalProvider><Consumer /></ModalProvider>)
    expect(screen.getByTestId('state')).toHaveTextContent('chiuso')
    expect(screen.queryByText('CORPO_MODALE')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'apri' }))
    expect(screen.getByText('CORPO_MODALE')).toBeInTheDocument()
    expect(screen.getByTestId('state')).toHaveTextContent('aperto')

    await userEvent.click(screen.getByRole('button', { name: 'chiudi' }))
    expect(screen.queryByText('CORPO_MODALE')).not.toBeInTheDocument()
    expect(screen.getByTestId('state')).toHaveTextContent('chiuso')
  })
})

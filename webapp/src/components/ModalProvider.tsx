import { createContext, useContext, useState, useCallback, useRef, type ReactNode } from 'react'

interface ModalOptions {
  content: ReactNode
  dismissible?: boolean
}

interface ModalContextValue {
  openModal: (options: ModalOptions) => void
  closeModal: () => void
  isModalOpen: boolean
}

const ModalContext = createContext<ModalContextValue | null>(null)

export function useModal() {
  const ctx = useContext(ModalContext)
  if (!ctx) throw new Error('useModal must be used within ModalProvider')
  return ctx
}

export default function ModalProvider({ children }: { children: ReactNode }) {
  const [stack, setStack] = useState<ModalOptions[]>([])
  const dragRef = useRef({ startY: 0, currentY: 0, dragging: false })
  const modalRef = useRef<HTMLDivElement>(null)

  const openModal = useCallback((options: ModalOptions) => {
    document.body.style.overflow = 'hidden'
    setStack((prev) => [...prev, { dismissible: true, ...options }])
  }, [])

  const closeModal = useCallback(() => {
    setStack((prev) => {
      const next = prev.slice(0, -1)
      if (next.length === 0) document.body.style.overflow = ''
      return next
    })
  }, [])

  const top = stack[stack.length - 1]

  // Swipe-down dismiss handlers
  const onTouchStart = useCallback((e: React.TouchEvent) => {
    dragRef.current = { startY: e.touches[0].clientY, currentY: e.touches[0].clientY, dragging: true }
  }, [])

  const onTouchMove = useCallback((e: React.TouchEvent) => {
    if (!dragRef.current.dragging) return
    const deltaY = e.touches[0].clientY - dragRef.current.startY
    dragRef.current.currentY = e.touches[0].clientY
    if (deltaY > 0 && modalRef.current) {
      modalRef.current.style.transform = `translateY(${deltaY}px)`
      modalRef.current.style.transition = 'none'
    }
  }, [])

  const onTouchEnd = useCallback(() => {
    const deltaY = dragRef.current.currentY - dragRef.current.startY
    dragRef.current.dragging = false
    if (modalRef.current) {
      modalRef.current.style.transition = 'transform 150ms ease'
      modalRef.current.style.transform = ''
    }
    if (deltaY > 120 && top?.dismissible) {
      closeModal()
    }
  }, [closeModal, top?.dismissible])

  return (
    <ModalContext.Provider value={{ openModal, closeModal, isModalOpen: stack.length > 0 }}>
      {children}
      {top && (
        <div
          className="fixed inset-0 bg-black/65 flex items-center justify-center p-4"
          style={{ zIndex: 50 + stack.length }}
          onClick={top.dismissible ? closeModal : undefined}
        >
          <div
            ref={modalRef}
            className="rounded-2xl bg-dnd-surface-elevated max-h-[85vh] overflow-y-auto w-full max-w-sm animate-modal-enter"
            style={{ WebkitOverflowScrolling: 'touch' }}
            onClick={(e) => e.stopPropagation()}
            onTouchStart={top.dismissible ? onTouchStart : undefined}
            onTouchMove={top.dismissible ? onTouchMove : undefined}
            onTouchEnd={top.dismissible ? onTouchEnd : undefined}
          >
            {top.content}
          </div>
        </div>
      )}
    </ModalContext.Provider>
  )
}

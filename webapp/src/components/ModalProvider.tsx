import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { m, AnimatePresence, useDragControls, type PanInfo } from 'framer-motion'
import { spring } from '@/styles/motion'

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

function ModalShell({
  options,
  onClose,
  depth,
}: {
  options: ModalOptions
  onClose: () => void
  depth: number
}) {
  const dragControls = useDragControls()
  const dismissible = options.dismissible !== false

  const handleDragEnd = (_: unknown, info: PanInfo) => {
    if (info.offset.y > 120 || info.velocity.y > 800) {
      if (dismissible) onClose()
    }
  }

  return (
    <m.div
      className="fixed inset-0 flex items-center justify-center p-4"
      style={{ zIndex: 50 + depth, background: 'var(--dnd-overlay)', backdropFilter: 'blur(6px)' }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      onClick={dismissible ? onClose : undefined}
    >
      <m.div
        className="relative rounded-3xl bg-gradient-parchment border border-dnd-border-strong surface-parchment
                   max-h-[85vh] overflow-hidden w-full max-w-sm shadow-parchment-2xl"
        initial={{ opacity: 0, scale: 0.9, y: 40 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.92, y: 20 }}
        transition={spring.swipe}
        drag={dismissible ? 'y' : false}
        dragConstraints={{ top: 0, bottom: 0 }}
        dragElastic={{ top: 0, bottom: 0.4 }}
        dragControls={dragControls}
        dragListener={false}
        onDragEnd={handleDragEnd}
        onClick={(e) => e.stopPropagation()}
      >
        {dismissible && (
          <div
            className="flex justify-center py-2 cursor-grab active:cursor-grabbing touch-none md:hidden"
            onPointerDown={(e) => dragControls.start(e)}
          >
            <div className="w-10 h-1 rounded-full bg-dnd-gold-dim/50" />
          </div>
        )}
        <div className="overflow-y-auto overscroll-contain max-h-[calc(85vh-2rem)]"
             style={{ WebkitOverflowScrolling: 'touch' }}>
          {options.content}
        </div>
      </m.div>
    </m.div>
  )
}

export default function ModalProvider({ children }: { children: ReactNode }) {
  const [stack, setStack] = useState<ModalOptions[]>([])

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

  return (
    <ModalContext.Provider value={{ openModal, closeModal, isModalOpen: stack.length > 0 }}>
      {children}
      <AnimatePresence>
        {stack.map((opts, i) => (
          <ModalShell
            key={i}
            options={opts}
            depth={i}
            onClose={closeModal}
          />
        ))}
      </AnimatePresence>
    </ModalContext.Provider>
  )
}

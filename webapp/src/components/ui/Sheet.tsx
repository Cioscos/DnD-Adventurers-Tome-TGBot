import React, { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { m, AnimatePresence, useDragControls, type PanInfo } from 'framer-motion'
import { X } from 'lucide-react'
import { spring } from '@/styles/motion'
import { useRegisterOverlay } from '@/store/overlayStore'
import { useOverlayDismiss } from '@/hooks/useOverlayDismiss'
import { useTranslation } from 'react-i18next'

interface SheetProps {
  open: boolean
  onClose: () => void
  children: React.ReactNode
  title?: string
  dismissible?: boolean
  /** If true, render as centered dialog instead of bottom sheet (desktop). */
  centered?: boolean
  className?: string
  /** z-index class of the backdrop wrapper. Override (e.g. 'z-[60]') when
   *  nesting a sheet above an already-open z-50 overlay. */
  zClassName?: string
}

/**
 * Modal bottom sheet (mobile) / centered dialog (desktop-md+).
 * Drag-to-dismiss on mobile via framer-motion drag controls.
 */
export default function Sheet({
  open,
  onClose,
  children,
  title,
  dismissible = true,
  centered = false,
  className = '',
  zClassName = 'z-50',
}: SheetProps) {
  const dragControls = useDragControls()
  const sheetRef = useRef<HTMLDivElement>(null)

  const { t } = useTranslation()
  useRegisterOverlay(open)
  // Escape e back/popstate chiudono solo lo sheet in cima allo stack condiviso.
  useOverlayDismiss(open, onClose, dismissible)

  // Prevent body scroll when open
  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  const handleDragEnd = (_: unknown, info: PanInfo) => {
    if (info.offset.y > 120 || info.velocity.y > 800) {
      if (dismissible) onClose()
    }
  }

  return createPortal(
    <AnimatePresence>
      {open && (
        <m.div
          key="sheet-backdrop"
          className={`fixed inset-0 ${zClassName} flex items-end md:items-center justify-center`}
          style={{ background: 'var(--dnd-overlay)', backdropFilter: 'blur(6px)' }}
          initial={{ opacity: 0, pointerEvents: 'none' }}
          animate={{ opacity: 1, pointerEvents: 'auto' }}
          // pointerEvents legato all'animazione: in chiusura il backdrop diventa
          // SUBITO click-through. Se un re-render concorrente (es. la lista che
          // cambia mentre lo Sheet esce) lascia l'AnimatePresence orfana — bug
          // noto di framer-motion con portal — il nodo resta a opacity 0 ma NON
          // intercetta più tap/scroll, quindi la pagina non si blocca.
          exit={{ opacity: 0, pointerEvents: 'none' }}
          transition={{ duration: 0.2 }}
          onClick={dismissible ? onClose : undefined}
        >
          <m.div
            ref={sheetRef}
            className={`
              relative w-full bg-gradient-parchment surface-parchment
              border-t border-dnd-border-strong md:border
              rounded-t-3xl md:rounded-3xl md:max-w-md
              shadow-parchment-2xl
              max-h-[85vh] overflow-hidden
              ${centered ? 'md:self-center' : ''}
              ${className}
            `}
            initial={centered ? { opacity: 0, scale: 0.96 } : { y: '100%' }}
            animate={centered ? { opacity: 1, scale: 1 } : { y: 0 }}
            exit={centered ? { opacity: 0, scale: 0.98 } : { y: '100%' }}
            transition={spring.swipe}
            drag={dismissible && !centered ? 'y' : false}
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.4 }}
            dragControls={dragControls}
            dragListener={false}
            onDragEnd={handleDragEnd}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Drag handle (mobile only) */}
            <div
              className="flex justify-center py-2 cursor-grab active:cursor-grabbing md:hidden touch-none"
              onPointerDown={(e) => dragControls.start(e)}
            >
              <div className="w-10 h-1 rounded-full bg-dnd-gold-dim/50" />
            </div>

            {title ? (
              <div className="relative px-5 pb-3 border-b border-dnd-border/50">
                <h2 className="font-display text-xl font-bold text-dnd-gold-bright text-center pr-8">
                  {title}
                </h2>
                {dismissible && (
                  <button
                    type="button"
                    onClick={onClose}
                    aria-label={t('common.close')}
                    className="absolute -top-1 right-2 w-10 h-10 flex items-center justify-center rounded-full text-dnd-gold-dim hover:text-dnd-gold-bright hover:bg-dnd-surface-raised transition-colors"
                  >
                    <X size={18} />
                  </button>
                )}
              </div>
            ) : (
              dismissible && (
                <div className="flex justify-end px-2 -mt-2">
                  <button
                    type="button"
                    onClick={onClose}
                    aria-label={t('common.close')}
                    className="w-10 h-10 flex items-center justify-center rounded-full text-dnd-gold-dim hover:text-dnd-gold-bright hover:bg-dnd-surface-raised transition-colors"
                  >
                    <X size={18} />
                  </button>
                </div>
              )
            )}

            <div className="overflow-y-auto overscroll-contain pb-safe-lg"
                 style={{ maxHeight: 'calc(85vh - 60px)' }}>
              {children}
            </div>
          </m.div>
        </m.div>
      )}
    </AnimatePresence>,
    document.body,
  )
}

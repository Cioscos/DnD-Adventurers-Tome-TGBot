import React from 'react'
import { createPortal } from 'react-dom'
import { m, AnimatePresence } from 'framer-motion'
import { spring } from '@/styles/motion'
import { CornerFlourishes } from './Ornament'
import { useRegisterOverlay } from '@/store/overlayStore'
import { useOverlayDismiss } from '@/hooks/useOverlayDismiss'
import { useDeferredBlur } from '@/hooks/useDeferredBlur'

export type DialogAccent = 'default' | 'gold' | 'crimson' | 'emerald' | 'arcane' | 'cobalt'
export type DialogSize = 'sm' | 'md'

interface ResultDialogProps {
  open: boolean
  onClose: () => void
  title?: React.ReactNode
  subtitle?: React.ReactNode
  accent?: DialogAccent
  pulse?: boolean
  size?: DialogSize
  children: React.ReactNode
  /** Slot for content rendered between body and OK button (e.g. inspiration button). */
  extraActions?: React.ReactNode
  /** Hide the default OK button (caller renders its own). */
  hideOkButton?: boolean
  okLabel?: string
}

const ACCENT_BORDER: Record<DialogAccent, string> = {
  default: 'border-dnd-gold-dim',
  gold: 'border-dnd-gold',
  crimson: 'border-dnd-crimson',
  emerald: 'border-dnd-emerald',
  arcane: 'border-dnd-arcane',
  cobalt: 'border-dnd-cobalt',
}

const SIZE_CLASS: Record<DialogSize, string> = {
  sm: 'max-w-xs',
  md: 'max-w-sm',
}

export default function ResultDialog({
  open,
  onClose,
  title,
  subtitle,
  accent = 'default',
  pulse = false,
  size = 'md',
  children,
  extraActions,
  hideOkButton = false,
  okLabel = 'OK',
}: ResultDialogProps) {
  useRegisterOverlay(open)
  // DESIGN.md §Dialogs: "Tap outside dismisses; ESC dismisses." Il back chiude
  // il dialogo invece di lasciare la pagina (finding #7/#12 audit FE).
  useOverlayDismiss(open, onClose)
  const { blurStyle, onEntranceComplete } = useDeferredBlur(open)

  const pulseClass = pulse
    ? accent === 'gold'
      ? 'animate-pulse-gold'
      : accent === 'crimson'
        ? 'animate-pulse-danger'
        : ''
    : ''

  // Portal su document.body: `position: fixed` si rompe dentro antenati con
  // transform (es. il track del CharacterSwiper, largo 300%) — la modale
  // finirebbe centrata sulla "pagina 2" del carosello.
  return createPortal(
    <AnimatePresence>
      {open && (
        <m.div
          className="fixed inset-0 flex items-center justify-center z-50 p-4"
          style={{ background: 'var(--dnd-overlay)', ...blurStyle }}
          onClick={onClose}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          onAnimationComplete={onEntranceComplete}
        >
          <m.div
            className={`relative rounded-3xl p-6 pt-7 w-full ${SIZE_CLASS[size]} space-y-4 text-center
                        bg-gradient-parchment surface-parchment border-2 ${ACCENT_BORDER[accent]} ${pulseClass}
                        shadow-parchment-2xl`}
            onClick={(e) => e.stopPropagation()}
            initial={{ opacity: 0, scale: 0.92, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 12 }}
            transition={spring.swipe}
          >
            <div className="text-dnd-gold-dim pointer-events-none">
              <CornerFlourishes />
            </div>

            {(title || subtitle) && (
              <div className="space-y-1">
                {title && (
                  <p className="text-sm text-dnd-text-muted font-cinzel uppercase tracking-widest">
                    {title}
                  </p>
                )}
                {subtitle && (
                  <p className="text-[11px] text-dnd-arcane-bright font-cinzel uppercase tracking-wider">
                    {subtitle}
                  </p>
                )}
              </div>
            )}

            {children}

            {extraActions}

            {!hideOkButton && (
              <m.button
                type="button"
                onClick={onClose}
                className="w-full py-2.5 rounded-xl bg-gradient-gold text-dnd-ink font-semibold
                           min-h-[48px] shadow-engrave font-cinzel uppercase tracking-wider"
                whileTap={{ scale: 0.97 }}
              >
                {okLabel}
              </m.button>
            )}
          </m.div>
        </m.div>
      )}
    </AnimatePresence>,
    document.body,
  )
}

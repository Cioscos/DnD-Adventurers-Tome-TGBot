import { createPortal } from 'react-dom'
import { Toaster as SonnerToaster } from 'sonner'

/**
 * Global toast toaster — mount once in main.tsx.
 * Themed to match the D&D parchment aesthetic.
 *
 * Portals to document.body and uses a high z-index so toasts paint above
 * modal Sheets (Sheet outer overlay sits at z-50 in body stacking context).
 */
export default function Toast() {
  if (typeof document === 'undefined') return null
  return createPortal(
    <SonnerToaster
      position="top-center"
      offset={24}
      mobileOffset={24}
      visibleToasts={3}
      closeButton
      richColors={false}
      style={{ zIndex: 9999 }}
      toastOptions={{
        style: {
          background: 'var(--dnd-surface-raised)',
          color: 'var(--dnd-text)',
          border: '1px solid var(--dnd-border-strong)',
          fontFamily: 'Fraunces, Georgia, serif',
          borderRadius: '12px',
          boxShadow: 'var(--shadow-4)',
        },
        className: 'font-body',
      }}
    />,
    document.body,
  )
}

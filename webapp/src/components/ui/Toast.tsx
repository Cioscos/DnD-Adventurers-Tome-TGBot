import { createPortal } from 'react-dom'
import { Toaster as SonnerToaster } from 'sonner'

/**
 * Global toast toaster — mount once in main.tsx.
 * Themed to match the D&D parchment aesthetic.
 *
 * Portals to document.body and uses a high z-index so toasts paint above
 * modal Sheets (Sheet outer overlay sits at z-50 in body stacking context).
 */
// In Telegram fullscreen i controlli nativi (Chiudi, ⋮) galleggiano sopra la
// app: un offset fisso di 24px metteva le toast (e il loro "Annulla") sotto di
// essi. Stesso termine max() di .pt-safe; fuori da Telegram vale ~24px.
const TOP_OFFSET =
  'calc(16px + max(env(safe-area-inset-top, 0px), var(--tg-safe-top, 0px) + var(--tg-content-top, 0px)))'

export default function Toast() {
  if (typeof document === 'undefined') return null
  return createPortal(
    <SonnerToaster
      position="top-center"
      offset={{ top: TOP_OFFSET }}
      mobileOffset={{ top: TOP_OFFSET }}
      expand
      visibleToasts={5}
      gap={8}
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
        classNames: { closeButton: 'dnd-toast-close' },
      }}
    />,
    document.body,
  )
}

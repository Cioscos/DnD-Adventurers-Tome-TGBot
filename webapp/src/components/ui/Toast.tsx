import { Toaster as SonnerToaster } from 'sonner'

/**
 * Global toast toaster — mount once in main.tsx.
 * Themed to match the D&D parchment aesthetic.
 */
export default function Toast() {
  return (
    <SonnerToaster
      position="bottom-center"
      offset={24}
      visibleToasts={3}
      closeButton
      richColors={false}
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
    />
  )
}

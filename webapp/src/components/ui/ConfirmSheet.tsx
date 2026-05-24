import React from 'react'
import Sheet from './Sheet'
import Button, { type ButtonVariant } from './Button'

interface ConfirmSheetProps {
  open: boolean
  onClose: () => void
  onConfirm: () => void
  title: string
  body?: React.ReactNode
  confirmLabel: string
  cancelLabel?: string
  confirmVariant?: ButtonVariant
  loading?: boolean
  centered?: boolean
}

/** Standard confirm dialog matching the bottom-sheet / centered modal pattern
 *  used across Inventory, Maps, Notes deletion flows. */
export default function ConfirmSheet({
  open,
  onClose,
  onConfirm,
  title,
  body,
  confirmLabel,
  cancelLabel,
  confirmVariant = 'danger',
  loading = false,
  centered = true,
}: ConfirmSheetProps) {
  return (
    <Sheet open={open} onClose={onClose} centered={centered} title={title}>
      <div className="p-5 space-y-4">
        {body && (
          <div className="text-sm text-dnd-text font-body text-center">
            {body}
          </div>
        )}
        <div className="flex gap-2">
          <Button
            variant={confirmVariant}
            fullWidth
            loading={loading}
            haptic={confirmVariant === 'danger' ? 'error' : 'success'}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
          <Button variant="secondary" fullWidth onClick={onClose}>
            {cancelLabel ?? 'Annulla'}
          </Button>
        </div>
      </div>
    </Sheet>
  )
}

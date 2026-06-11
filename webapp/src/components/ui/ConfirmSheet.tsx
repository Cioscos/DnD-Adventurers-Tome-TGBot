import React from 'react'
import { useTranslation } from 'react-i18next'
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
  const { t } = useTranslation()
  return (
    <Sheet open={open} onClose={onClose} centered={centered} title={title}>
      <div className="p-5 space-y-4">
        {body && (
          <div className="text-sm text-dnd-text font-body text-center">
            {body}
          </div>
        )}
        {/* Annulla a sinistra, conferma a destra (convenzione: l'azione di conferma sta sempre a destra). */}
        <div className="flex gap-2">
          <Button variant="secondary" fullWidth onClick={onClose}>
            {cancelLabel ?? t('common.cancel')}
          </Button>
          <Button
            variant={confirmVariant}
            fullWidth
            loading={loading}
            haptic={confirmVariant === 'danger' ? 'error' : 'success'}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </Sheet>
  )
}

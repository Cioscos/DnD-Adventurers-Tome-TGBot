import { toast } from 'sonner'
import { Undo2 } from 'lucide-react'

interface ShowUndoToastOpts {
  /** Headline (e.g. "Personaggio eliminato"). */
  message: string
  /** Button label, e.g. "Annulla". */
  actionLabel: string
  /** Fires when the user clicks the undo action. */
  onUndo: () => void
  /** Milliseconds before the toast auto-dismisses (and the original action is finalized). */
  durationMs?: number
}

/** Show a 5-second toast with an "Annulla" action.
 *  Caller is responsible for any optimistic UI rollback inside `onUndo`. */
export function showUndoToast({ message, actionLabel, onUndo, durationMs = 5000 }: ShowUndoToastOpts): void {
  toast(message, {
    duration: durationMs,
    action: {
      label: actionLabel,
      onClick: () => {
        onUndo()
      },
    },
    icon: <Undo2 size={16} />,
    className: 'border-dnd-gold-dim/40',
  })
}

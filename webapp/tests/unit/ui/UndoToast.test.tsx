import { describe, it, expect, vi } from 'vitest'
import { toast } from 'sonner'
import { showUndoToast } from '@/components/ui/UndoToast'

vi.mock('sonner', () => ({ toast: vi.fn() }))

describe('showUndoToast', () => {
  it('shows a toast with the message, an undo action and the default 5s duration', () => {
    const onUndo = vi.fn()
    showUndoToast({ message: 'Eliminato', actionLabel: 'Annulla', onUndo })
    expect(toast).toHaveBeenCalledTimes(1)
    const [msg, opts] = vi.mocked(toast).mock.calls[0] as [string, { duration: number; action: { label: string; onClick: () => void } }]
    expect(msg).toBe('Eliminato')
    expect(opts.duration).toBe(5000)
    expect(opts.action.label).toBe('Annulla')
    // invoking the action fires the undo callback
    opts.action.onClick()
    expect(onUndo).toHaveBeenCalledTimes(1)
  })

  it('honors a custom duration', () => {
    showUndoToast({ message: 'm', actionLabel: 'a', onUndo: () => {}, durationMs: 8000 })
    const [, opts] = vi.mocked(toast).mock.calls.at(-1) as [string, { duration: number }]
    expect(opts.duration).toBe(8000)
  })
})

import { useRef, useCallback } from 'react'

interface UseLongPressOpts {
  onLongPress: () => void
  /** Short click handler. Fires if pointer released before threshold. */
  onClick?: () => void
  /** Hold duration in ms. */
  thresholdMs?: number
  /** Receives a value in [0,1] during the hold so the caller can render a progress ring.
   *  When provided, the hook polls at ~30Hz to keep the ring smooth. */
  onProgress?: (p: number) => void
}

/** Returns event handlers for a long-press detector that distinguishes
 *  short tap from sustained press. Works for touch and mouse. */
export function useLongPress({ onLongPress, onClick, thresholdMs = 500, onProgress }: UseLongPressOpts) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const triggeredRef = useRef(false)

  const clearTimers = useCallback(() => {
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null }
    if (pollRef.current) { clearTimeout(pollRef.current); pollRef.current = null }
  }, [])

  const start = useCallback(() => {
    triggeredRef.current = false
    clearTimers()
    if (onProgress) {
      onProgress(0)
      const startTs = Date.now()
      const tick = () => {
        const elapsed = Date.now() - startTs
        const p = Math.min(elapsed / thresholdMs, 1)
        onProgress(p)
        if (p >= 1) {
          triggeredRef.current = true
          onLongPress()
          return
        }
        pollRef.current = setTimeout(tick, 30)
      }
      pollRef.current = setTimeout(tick, 30)
    } else {
      timerRef.current = setTimeout(() => {
        triggeredRef.current = true
        onLongPress()
      }, thresholdMs)
    }
  }, [onLongPress, thresholdMs, onProgress, clearTimers])

  const cancel = useCallback(() => {
    clearTimers()
    if (onProgress) onProgress(0)
  }, [clearTimers, onProgress])

  const end = useCallback(() => {
    cancel()
    if (!triggeredRef.current && onClick) onClick()
  }, [cancel, onClick])

  return {
    onPointerDown: start,
    onPointerUp: end,
    onPointerLeave: cancel,
    onPointerCancel: cancel,
    onTouchStart: start,
    onTouchEnd: end,
    onTouchCancel: cancel,
  }
}

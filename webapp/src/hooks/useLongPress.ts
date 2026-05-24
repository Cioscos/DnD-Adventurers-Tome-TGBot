import { useRef, useCallback } from 'react'

interface UseLongPressOpts {
  onLongPress: () => void
  /** Short click handler. Fires if pointer released before threshold. */
  onClick?: () => void
  /** Hold duration in ms. */
  thresholdMs?: number
}

/** Returns event handlers for a long-press detector that distinguishes
 *  short tap from sustained press. Works for touch and mouse. */
export function useLongPress({ onLongPress, onClick, thresholdMs = 500 }: UseLongPressOpts) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const triggeredRef = useRef(false)

  const start = useCallback(() => {
    triggeredRef.current = false
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      triggeredRef.current = true
      onLongPress()
    }, thresholdMs)
  }, [onLongPress, thresholdMs])

  const cancel = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

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

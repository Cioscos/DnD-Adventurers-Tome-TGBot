import { useRef, useCallback } from 'react'

interface UseLongPressOpts {
  onLongPress: () => void
  /** Short click handler. Fires if pointer released before threshold AND without moving. */
  onClick?: () => void
  /** Hold duration in ms. */
  thresholdMs?: number
  /** Receives a value in [0,1] during the hold so the caller can render a progress ring.
   *  When provided, the hook polls at ~30Hz to keep the ring smooth. */
  onProgress?: (p: number) => void
}

/** Pixels of movement after press-down that cancel the tap/long-press (treat as scroll). */
const MOVE_CANCEL_PX = 12

/** Milliseconds before the progress ring starts filling (so a quick scroll touch never
 *  visibly starts the ring). Progress is rescaled so it still reaches 1 at thresholdMs. */
const RING_DELAY_MS = 120

type AnyPressEvent =
  | React.PointerEvent
  | React.TouchEvent

function eventXY(e: AnyPressEvent): { x: number; y: number } {
  if ('touches' in e && e.touches.length > 0) {
    return { x: e.touches[0].clientX, y: e.touches[0].clientY }
  }
  const pe = e as React.PointerEvent
  return { x: pe.clientX, y: pe.clientY }
}

/** Returns event handlers for a long-press detector that distinguishes
 *  short tap from sustained press, and cancels both if the finger moves
 *  (so scrolling never registers as a tap). Works for touch and mouse. */
export function useLongPress({ onLongPress, onClick, thresholdMs = 500, onProgress }: UseLongPressOpts) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const triggeredRef = useRef(false)
  const movedRef = useRef(false)
  const startRef = useRef({ x: 0, y: 0 })
  const pressingRef = useRef(false)

  const clearTimers = useCallback(() => {
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null }
    if (pollRef.current) { clearTimeout(pollRef.current); pollRef.current = null }
  }, [])

  const start = useCallback((e: AnyPressEvent) => {
    // Gesture already tracked (devices fire both pointer+touch families for one physical
    // touch) — ignore the duplicate so we don't reset movedRef/startRef mid-gesture and
    // mis-register a scroll as a tap.
    if (pressingRef.current) return
    pressingRef.current = true
    triggeredRef.current = false
    movedRef.current = false
    startRef.current = eventXY(e)
    clearTimers()
    if (onProgress) {
      onProgress(0)
      const startTs = Date.now()
      const tick = () => {
        const elapsed = Date.now() - startTs
        // Delay the ring: stay at 0 for the first RING_DELAY_MS, then rescale
        // so the ring still completes exactly when elapsed == thresholdMs.
        const p = elapsed <= RING_DELAY_MS
          ? 0
          : Math.min((elapsed - RING_DELAY_MS) / Math.max(1, thresholdMs - RING_DELAY_MS), 1)
        onProgress(p)
        if (elapsed >= thresholdMs) {
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
    pressingRef.current = false
    clearTimers()
    if (onProgress) onProgress(0)
  }, [clearTimers, onProgress])

  const move = useCallback((e: AnyPressEvent) => {
    if (!pressingRef.current || movedRef.current) return
    const { x, y } = eventXY(e)
    if (Math.abs(x - startRef.current.x) > MOVE_CANCEL_PX ||
        Math.abs(y - startRef.current.y) > MOVE_CANCEL_PX) {
      movedRef.current = true
      cancel() // moving → not a tap, not a long-press
    }
  }, [cancel])

  const end = useCallback(() => {
    cancel()
    if (!triggeredRef.current && !movedRef.current && onClick) onClick()
  }, [cancel, onClick])

  // Register BOTH Pointer and Touch move handlers: some Telegram in-app webviews
  // deliver only Touch events, others only Pointer. The pressingRef + movedRef
  // guards make the duplicate delivery a harmless single-cancel.
  return {
    onPointerDown: start,
    onPointerMove: move,
    onPointerUp: end,
    onPointerLeave: cancel,
    onPointerCancel: cancel,
    onTouchStart: start,
    onTouchMove: move,
    onTouchEnd: end,
    onTouchCancel: cancel,
  }
}

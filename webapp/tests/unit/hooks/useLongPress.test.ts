import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type React from 'react'
import { renderHook } from '@testing-library/react'
import { useLongPress } from '@/hooks/useLongPress'

// Minimal synthetic press event — the hook only reads clientX/clientY (or
// `touches` when present). Casting through `unknown` keeps it lint-clean.
const evt = (x = 0, y = 0) => ({ clientX: x, clientY: y }) as unknown as React.PointerEvent

describe('useLongPress', () => {
  beforeEach(() => {
    // Fake `Date` too: the onProgress poll computes elapsed via Date.now(), so the
    // clock must advance alongside the timers when we call advanceTimersByTime.
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] })
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('fires onClick for a quick tap (release before threshold, no movement)', () => {
    const onClick = vi.fn()
    const onLongPress = vi.fn()
    const { result } = renderHook(() => useLongPress({ onClick, onLongPress, thresholdMs: 500 }))

    result.current.onPointerDown(evt(0, 0))
    result.current.onPointerUp()

    expect(onClick).toHaveBeenCalledTimes(1)
    expect(onLongPress).not.toHaveBeenCalled()
  })

  it('fires onLongPress after the threshold and suppresses the trailing onClick', () => {
    const onClick = vi.fn()
    const onLongPress = vi.fn()
    const { result } = renderHook(() => useLongPress({ onClick, onLongPress, thresholdMs: 500 }))

    result.current.onPointerDown(evt(0, 0))
    vi.advanceTimersByTime(500)
    expect(onLongPress).toHaveBeenCalledTimes(1)

    // Release AFTER the long-press already triggered must not also fire onClick.
    result.current.onPointerUp()
    expect(onClick).not.toHaveBeenCalled()
  })

  it('cancels tap and long-press when the finger moves past the 12px threshold (scroll)', () => {
    const onClick = vi.fn()
    const onLongPress = vi.fn()
    const { result } = renderHook(() => useLongPress({ onClick, onLongPress, thresholdMs: 500 }))

    result.current.onPointerDown(evt(0, 0))
    result.current.onPointerMove(evt(20, 0)) // 20px > 12px → treat as scroll
    result.current.onPointerUp()
    vi.advanceTimersByTime(500)

    expect(onClick).not.toHaveBeenCalled()
    expect(onLongPress).not.toHaveBeenCalled()
  })

  it('still taps when movement stays within the 12px threshold', () => {
    const onClick = vi.fn()
    const onLongPress = vi.fn()
    const { result } = renderHook(() => useLongPress({ onClick, onLongPress, thresholdMs: 500 }))

    result.current.onPointerDown(evt(0, 0))
    result.current.onPointerMove(evt(5, 5)) // within threshold
    result.current.onPointerUp()

    expect(onClick).toHaveBeenCalledTimes(1)
  })

  // Regression (see memory: useLongPress cancel-then-end). A pointercancel fired
  // BEFORE the move threshold cleared `pressingRef`; a stray touchend afterwards
  // must NOT re-register as a tap.
  it('does not fire onClick when pointercancel precedes a stray touchend', () => {
    const onClick = vi.fn()
    const onLongPress = vi.fn()
    const { result } = renderHook(() => useLongPress({ onClick, onLongPress, thresholdMs: 500 }))

    result.current.onPointerDown(evt(0, 0))
    result.current.onPointerCancel() // browser aborted the gesture
    result.current.onTouchEnd() // stray end from the dual touch+pointer delivery

    expect(onClick).not.toHaveBeenCalled()
  })

  it('emits a single onClick under dual pointer+touch delivery (no double-fire)', () => {
    const onClick = vi.fn()
    const onLongPress = vi.fn()
    const { result } = renderHook(() => useLongPress({ onClick, onLongPress, thresholdMs: 500 }))

    // One physical touch delivered as both families: the second start is ignored
    // by the pressingRef guard.
    result.current.onPointerDown(evt(0, 0))
    result.current.onTouchStart(evt(0, 0))
    result.current.onPointerUp() // fires onClick + clears pressingRef
    result.current.onTouchEnd() // wasActive === false → no second onClick

    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('drives the progress ring and fires onLongPress at the threshold (onProgress path)', () => {
    const onLongPress = vi.fn()
    const onProgress = vi.fn()
    const { result } = renderHook(() =>
      useLongPress({ onLongPress, onProgress, thresholdMs: 500 }),
    )

    result.current.onPointerDown(evt(0, 0))
    expect(onProgress).toHaveBeenCalledWith(0) // ring starts empty

    // The poll fires ~every 30ms, so the tick whose elapsed crosses the 500ms
    // threshold lands just past it — advance generously to cover that tick.
    vi.advanceTimersByTime(600)
    expect(onLongPress).toHaveBeenCalledTimes(1)
    // Ring reached a filled value at some point during the hold.
    const maxP = Math.max(...onProgress.mock.calls.map((c) => c[0] as number))
    expect(maxP).toBeGreaterThan(0)
  })

  it('resets the ring to 0 on cancel', () => {
    const onLongPress = vi.fn()
    const onProgress = vi.fn()
    const { result } = renderHook(() =>
      useLongPress({ onLongPress, onProgress, thresholdMs: 500 }),
    )

    result.current.onPointerDown(evt(0, 0))
    onProgress.mockClear()
    result.current.onPointerLeave() // cancel
    expect(onProgress).toHaveBeenLastCalledWith(0)

    vi.advanceTimersByTime(500)
    expect(onLongPress).not.toHaveBeenCalled() // poll timer was cleared
  })
})

import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useIntersection } from '@/hooks/useIntersection'

let ioCallback: ((entries: { isIntersecting: boolean }[]) => void) | null = null
let disconnected = false

beforeEach(() => {
  ioCallback = null
  disconnected = false
  class IO {
    constructor(cb: (entries: { isIntersecting: boolean }[]) => void) {
      ioCallback = cb
    }
    observe() {}
    unobserve() {}
    disconnect() {
      disconnected = true
    }
  }
  ;(globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = IO
})

describe('useIntersection', () => {
  it('is false until the element intersects, then true', () => {
    const ref = { current: document.createElement('div') }
    const { result } = renderHook(() => useIntersection(ref))
    expect(result.current).toBe(false)
    act(() => ioCallback?.([{ isIntersecting: true }]))
    expect(result.current).toBe(true)
  })

  it('disconnects after the first intersection when once=true', () => {
    const ref = { current: document.createElement('div') }
    renderHook(() => useIntersection(ref, { once: true }))
    act(() => ioCallback?.([{ isIntersecting: true }]))
    expect(disconnected).toBe(true)
  })
})

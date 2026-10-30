import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useIsScrolling } from '@/hooks/useIsScrolling'

const scrollTo = (el: HTMLElement, top: number, left = 0) => {
  el.scrollTop = top
  el.scrollLeft = left
  act(() => { el.dispatchEvent(new Event('scroll')) })
}
const touch = (type: string, touches = 0) => {
  const e = new Event(type) as Event & { touches: unknown[] }
  e.touches = new Array(touches)
  act(() => { window.dispatchEvent(e) })
}
const wait = (ms: number) => act(() => { vi.advanceTimersByTime(ms) })

describe('useIsScrolling', () => {
  let el: HTMLElement

  beforeEach(() => {
    vi.useFakeTimers()
    el = document.createElement('div')
    document.body.appendChild(el)
  })
  afterEach(() => {
    el.remove()
    vi.useRealTimers()
  })

  it('si spegne dopo una pausa senza scroll, non durante una breve', () => {
    const { result } = renderHook(() => useIsScrolling())
    scrollTo(el, 50)
    expect(result.current).toBe(true)
    wait(700)
    expect(result.current).toBe(true)
    scrollTo(el, 80)
    wait(700)
    expect(result.current).toBe(true)
    wait(150)
    expect(result.current).toBe(false)
  })

  it('resta attivo col dito fermo sullo schermo, si spegne dopo il rilascio', () => {
    const { result } = renderHook(() => useIsScrolling())
    touch('touchstart', 1)
    scrollTo(el, 50)
    wait(5000)
    expect(result.current).toBe(true)
    touch('touchend')
    wait(850)
    expect(result.current).toBe(false)
  })

  it('ignora lo scroll orizzontale', () => {
    const { result } = renderHook(() => useIsScrolling())
    scrollTo(el, 0, 120)
    expect(result.current).toBe(false)
  })
})

import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useDeferredBlur } from '@/hooks/useDeferredBlur'

describe('useDeferredBlur', () => {
  it('nessun blur prima del completamento dell\'ingresso', () => {
    const { result } = renderHook(() => useDeferredBlur(true))
    expect(result.current.blurStyle.backdropFilter).toBeUndefined()
  })

  it('blur attivo dopo onEntranceComplete', () => {
    const { result } = renderHook(() => useDeferredBlur(true))
    act(() => result.current.onEntranceComplete())
    expect(result.current.blurStyle.backdropFilter).toBe('blur(6px)')
    expect(result.current.blurStyle.WebkitBackdropFilter).toBe('blur(6px)')
  })

  it('blur rimosso appena visible torna false, e la riapertura riparte senza blur', () => {
    const { result, rerender } = renderHook(({ v }) => useDeferredBlur(v), {
      initialProps: { v: true },
    })
    act(() => result.current.onEntranceComplete())
    rerender({ v: false })
    expect(result.current.blurStyle.backdropFilter).toBeUndefined()
    rerender({ v: true })
    expect(result.current.blurStyle.backdropFilter).toBeUndefined()
  })

  it('onEntranceComplete durante l\'uscita (visible=false) non accende il blur', () => {
    const { result, rerender } = renderHook(({ v }) => useDeferredBlur(v), {
      initialProps: { v: false },
    })
    act(() => result.current.onEntranceComplete())
    expect(result.current.blurStyle.backdropFilter).toBeUndefined()
    rerender({ v: false })
    expect(result.current.blurStyle.backdropFilter).toBeUndefined()
  })

  it('raggio personalizzato', () => {
    const { result } = renderHook(() => useDeferredBlur(true, 10))
    act(() => result.current.onEntranceComplete())
    expect(result.current.blurStyle.backdropFilter).toBe('blur(10px)')
  })
})

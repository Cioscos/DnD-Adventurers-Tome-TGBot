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

  it('la riapertura dopo un ciclo completo open→close→exit-complete non riaccende subito il blur (istanza persistente, es. Sheet/ResultDialog)', () => {
    // Riproduce l'ordine reale di framer-motion su un overlay controllato da
    // `open` la cui istanza NON si smonta alla chiusura: onAnimationComplete
    // scatta anche a fine EXIT, quindi onEntranceComplete viene richiamato
    // una seconda volta mentre visible=false, dopo che l'effect ha già
    // resettato `entered`. Senza guardia questo "ri-arma" entered=true e la
    // riapertura successiva mostra il blur dal primo frame (bug segnalato in
    // review: task-8-review.md, Important #1).
    const { result, rerender } = renderHook(({ v }) => useDeferredBlur(v), {
      initialProps: { v: true },
    })
    act(() => result.current.onEntranceComplete()) // 1. ingresso completo, blur ON
    rerender({ v: false }) // 2. chiusura: effect resetta entered, blur OFF
    act(() => result.current.onEntranceComplete()) // 3. onAnimationComplete dell'EXIT (framer-motion)
    expect(result.current.blurStyle.backdropFilter).toBeUndefined()
    rerender({ v: true }) // 4. riapertura
    expect(result.current.blurStyle.backdropFilter).toBeUndefined()
  })

  it('raggio personalizzato', () => {
    const { result } = renderHook(() => useDeferredBlur(true, 10))
    act(() => result.current.onEntranceComplete())
    expect(result.current.blurStyle.backdropFilter).toBe('blur(10px)')
  })
})

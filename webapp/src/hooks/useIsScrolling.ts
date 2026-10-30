import { useEffect, useState } from 'react'

/** Attesa dopo l'ultimo scroll prima di considerarlo finito: copre le pause
 *  brevi di uno scroll lento, che altrimenti farebbero lampeggiare chi lo usa. */
const IDLE_MS = 800

/**
 * true mentre la pagina scorre in VERTICALE. Listener in capture su window perché
 * lo scroll non fa bubbling e i contenitori sono annidati (<main> del Layout,
 * schermate dello swiper...). Lo scroll orizzontale (chip, breadcrumb) non conta.
 * Finché il dito resta sullo schermo lo scroll non è finito, anche se è fermo.
 */
export function useIsScrolling(): boolean {
  const [scrolling, setScrolling] = useState(false)

  useEffect(() => {
    let idleTimer: ReturnType<typeof setTimeout> | null = null
    let touching = false
    const lastTop = new WeakMap<EventTarget, number>()

    const clearIdle = () => {
      if (idleTimer) clearTimeout(idleTimer)
      idleTimer = null
    }
    const armIdle = () => {
      clearIdle()
      idleTimer = setTimeout(() => setScrolling(false), IDLE_MS)
    }
    const onScroll = (e: Event) => {
      const target = e.target
      if (!target) return
      const top = target instanceof Element ? target.scrollTop : window.scrollY
      const moved = top !== (lastTop.get(target) ?? 0)
      lastTop.set(target, top)
      if (!moved) return
      setScrolling(true)
      if (touching) clearIdle()
      else armIdle()
    }
    const onTouchStart = () => {
      touching = true
      clearIdle()
    }
    const onTouchEnd = (e: TouchEvent) => {
      if (e.touches.length > 0) return
      touching = false
      armIdle()
    }

    window.addEventListener('scroll', onScroll, { capture: true, passive: true })
    window.addEventListener('touchstart', onTouchStart, { capture: true, passive: true })
    window.addEventListener('touchend', onTouchEnd, { capture: true, passive: true })
    window.addEventListener('touchcancel', onTouchEnd, { capture: true, passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll, { capture: true })
      window.removeEventListener('touchstart', onTouchStart, { capture: true })
      window.removeEventListener('touchend', onTouchEnd, { capture: true })
      window.removeEventListener('touchcancel', onTouchEnd, { capture: true })
      clearIdle()
    }
  }, [])

  return scrolling
}

import { useEffect, useState, type RefObject } from 'react'

/**
 * Returns true when the observed element enters the viewport.
 * Once=true disconnects after first intersection (one-shot reveal).
 */
export function useIntersection(
  ref: RefObject<Element>,
  options: IntersectionObserverInit & { once?: boolean } = {}
): boolean {
  const [isIntersecting, setIntersecting] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const { once, ...ioOptions } = options
    const observer = new IntersectionObserver(([entry]) => {
      setIntersecting(entry.isIntersecting)
      if (entry.isIntersecting && once) observer.disconnect()
    }, ioOptions)
    observer.observe(el)
    return () => observer.disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ref])

  return isIntersecting
}

import { useEffect, useRef } from 'react'

/**
 * true finché il componente non ha ancora mostrato un valore definito. Serve ai
 * "pop" dei numeri (m.span key={valore}): l'animazione deve marcare un CAMBIO,
 * non ripartire a ogni visita della pagina o all'arrivo dei dati →
 * `initial={isFirst ? false : {...}}`.
 */
export function useIsFirstValue(value: unknown): boolean {
  const seen = useRef(false)
  const isFirst = !seen.current
  useEffect(() => {
    if (value !== undefined && value !== null) seen.current = true
  }, [value])
  return isFirst
}

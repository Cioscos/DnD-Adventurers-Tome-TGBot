import { useCallback, useEffect, useState } from 'react'
import type { CSSProperties } from 'react'

/**
 * Blur del backdrop rinviato a fine animazione di ingresso.
 *
 * Animare l'opacità di un layer con `backdrop-filter` costringe la WebView
 * Android a ricalcolare il blur dell'intera pagina a ogni frame (jank +
 * flicker — vedi baseline perf). Il velo scuro anima da solo; il blur si
 * accende quando l'overlay è fermo (onEntranceComplete) e si spegne appena
 * parte l'uscita (visible=false).
 */
export function useDeferredBlur(
  visible: boolean,
  radiusPx = 6,
): { blurStyle: CSSProperties; onEntranceComplete: () => void } {
  const [entered, setEntered] = useState(false)

  useEffect(() => {
    if (!visible) setEntered(false)
  }, [visible])

  const onEntranceComplete = useCallback(() => setEntered(true), [])

  const on = visible && entered
  return {
    blurStyle: on
      ? {
          backdropFilter: `blur(${radiusPx}px)`,
          WebkitBackdropFilter: `blur(${radiusPx}px)`,
        }
      : {},
    onEntranceComplete,
  }
}

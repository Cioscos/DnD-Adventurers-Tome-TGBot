import { useCallback, useEffect, useRef, useState } from 'react'
import type { CSSProperties } from 'react'

/**
 * Blur del backdrop rinviato a fine animazione di ingresso.
 *
 * Animare l'opacità di un layer con `backdrop-filter` costringe la WebView
 * Android a ricalcolare il blur dell'intera pagina a ogni frame (jank +
 * flicker — vedi baseline perf). Il velo scuro anima da solo; il blur si
 * accende quando l'overlay è fermo (onEntranceComplete) e si spegne appena
 * parte l'uscita (visible=false).
 *
 * Su overlay a istanza persistente (`open` controllato dall'esterno, es.
 * Sheet/ResultDialog) framer-motion richiama `onAnimationComplete` anche a
 * fine EXIT: senza guardia, quella seconda chiamata "ri-arma" `entered=true`
 * mentre invisible, e la riapertura successiva mostrerebbe il blur dal primo
 * frame invece che a fine ingresso (task-8-review.md, Important #1). La ref
 * garantisce che solo un completamento mentre visible=true riaccenda il blur.
 */
export function useDeferredBlur(
  visible: boolean,
  radiusPx = 6,
): { blurStyle: CSSProperties; onEntranceComplete: () => void } {
  const [entered, setEntered] = useState(false)
  const visibleRef = useRef(visible)
  visibleRef.current = visible

  useEffect(() => {
    if (!visible) setEntered(false)
  }, [visible])

  const onEntranceComplete = useCallback(() => {
    if (visibleRef.current) setEntered(true)
  }, [])

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

import { useEffect, useState } from 'react'

/**
 * Tracks Telegram Mini App viewport height changes (keyboard open/close).
 * Exposes --tg-vh CSS variable so layout can use `min-h-[var(--tg-vh)]`.
 */
export function useTelegramViewport(): number {
  const [vh, setVh] = useState<number>(() =>
    typeof window !== 'undefined' ? window.innerHeight : 0
  )

  useEffect(() => {
    const handler = () => {
      const tg = window.Telegram?.WebApp
      const h = tg?.viewportStableHeight ?? tg?.viewportHeight ?? window.innerHeight
      setVh(h)
      document.documentElement.style.setProperty('--tg-vh', `${h}px`)
    }
    handler()
    window.Telegram?.WebApp?.onEvent?.('viewportChanged', handler)
    window.addEventListener('resize', handler)
    return () => {
      window.Telegram?.WebApp?.offEvent?.('viewportChanged', handler)
      window.removeEventListener('resize', handler)
    }
  }, [])

  return vh
}

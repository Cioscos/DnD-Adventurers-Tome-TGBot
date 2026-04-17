let loaded: Promise<unknown> | null = null

export function preloadDiceScene(): Promise<unknown> {
  if (!loaded) {
    loaded = import('./DiceScene').catch((err) => {
      loaded = null
      throw err
    })
  }
  return loaded
}

export function schedulePreloadDiceScene(): void {
  const run = () => {
    void preloadDiceScene()
  }
  if (typeof window === 'undefined') return
  const ric = (window as Window & { requestIdleCallback?: (cb: () => void) => void })
    .requestIdleCallback
  if (typeof ric === 'function') ric(run)
  else setTimeout(run, 800)
}

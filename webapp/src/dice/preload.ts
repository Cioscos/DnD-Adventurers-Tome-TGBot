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
    // Un errore qui non conta: se il chunk manca, lo gestisce il primo tiro.
    preloadDiceScene().catch(() => {})
  }
  if (typeof window === 'undefined') return
  const ric = (window as Window & { requestIdleCallback?: (cb: () => void) => void })
    .requestIdleCallback
  if (typeof ric === 'function') ric(run)
  else setTimeout(run, 800)
}

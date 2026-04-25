import { useThemeSettings, type ThemeMode } from '@/store/themeSettings'

type ResolvedTheme = 'dark' | 'light'

/**
 * Resolve a ThemeMode to a concrete theme.
 * - 'dark' / 'light' → user's explicit choice
 * - 'auto' inside Telegram → follow Telegram.WebApp.colorScheme
 * - 'auto' outside Telegram → 'light' (matches local-dev default expectation)
 */
export function resolveTheme(mode: ThemeMode): ResolvedTheme {
  if (mode === 'dark' || mode === 'light') return mode
  const tgScheme = window.Telegram?.WebApp?.colorScheme
  if (tgScheme === 'dark' || tgScheme === 'light') return tgScheme
  return 'light'
}

/** Apply current theme to <html> by toggling the .light class. */
export function applyTheme(): void {
  const mode = useThemeSettings.getState().mode
  const resolved = resolveTheme(mode)
  document.documentElement.classList.toggle('light', resolved === 'light')
}

/**
 * Initialize the theme system. Call once on startup.
 * - Apply the current theme.
 * - Subscribe to store changes → re-apply on user toggle.
 * - Listen to Telegram themeChanged → re-apply only when mode === 'auto'.
 */
export function initTheme(): void {
  applyTheme()
  useThemeSettings.subscribe(() => applyTheme())
  window.Telegram?.WebApp?.onEvent?.('themeChanged', () => {
    if (useThemeSettings.getState().mode === 'auto') {
      applyTheme()
    }
  })
}

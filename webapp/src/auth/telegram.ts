/**
 * Telegram Mini App auth helpers.
 *
 * The global `window.Telegram.WebApp` object is injected by the Telegram client
 * when the page is opened as a Mini App. During local development it is absent,
 * so we fall back to empty values so the app can still render.
 */

declare global {
  interface Window {
    Telegram: {
      WebApp: TelegramWebApp
    }
  }
}

interface TelegramWebApp {
  initData: string
  platform?: string
  version?: string
  initDataUnsafe: {
    user?: {
      id: number
      first_name: string
      last_name?: string
      username?: string
      language_code?: string
    }
    auth_date: number
    hash: string
    /** Parametro startapp dei deep link t.me/<bot>?startapp=… */
    start_param?: string
  }
  colorScheme: 'light' | 'dark'
  themeParams: Record<string, string>
  isExpanded: boolean
  viewportHeight: number
  viewportStableHeight?: number
  // Fullscreen mode + safe areas (Bot API 8.0+). Optional: absent on older clients.
  isFullscreen?: boolean
  safeAreaInset?: { top: number; bottom: number; left: number; right: number }
  contentSafeAreaInset?: { top: number; bottom: number; left: number; right: number }
  setHeaderColor?(color: string): void
  MainButton: {
    text: string
    color: string
    textColor: string
    isVisible: boolean
    isActive: boolean
    show(): void
    hide(): void
    enable(): void
    disable(): void
    onClick(callback: () => void): void
    offClick(callback: () => void): void
    setText(text: string): void
  }
  BackButton: {
    isVisible: boolean
    show(): void
    hide(): void
    onClick(callback: () => void): void
    offClick(callback: () => void): void
  }
  onEvent(eventType: string, callback: () => void): void
  offEvent(eventType: string, callback: () => void): void
  ready(): void
  expand(): void
  close(): void
  // Vertical-swipe gesture control (Bot API 7.7+). Optional: absent on older
  // clients. Disabling stops Telegram from dragging the whole webview frame on a
  // fast vertical scroll (which slides the top bar under the native controls).
  disableVerticalSwipes?(): void
  enableVerticalSwipes?(): void
  isVerticalSwipesEnabled?: boolean
  sendData(data: string): void
  showAlert(message: string, callback?: () => void): void
  showConfirm(message: string, callback: (confirmed: boolean) => void): void
  /** Condivide un messaggio preparato (Bot API 8.0+) via picker nativo. */
  shareMessage?(msgId: string, callback?: (sent: boolean) => void): void
  showPopup(params: object, callback?: (id: string) => void): void
  HapticFeedback: {
    impactOccurred(style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft'): void
    notificationOccurred(type: 'error' | 'success' | 'warning'): void
    selectionChanged(): void
  }
}

const twa: TelegramWebApp | null =
  typeof window !== 'undefined' && window.Telegram?.WebApp
    ? window.Telegram.WebApp
    : null

/** Raw initData string for use as the X-Telegram-Init-Data header. */
export function getInitData(): string {
  // Always read from the live window.Telegram.WebApp reference to avoid
  // stale-capture issues: when the Mini App is opened via a reply keyboard
  // button, Telegram may inject window.Telegram.WebApp *after* this module
  // has been evaluated (twa would be null). Reading dynamically guarantees
  // we get the current initData regardless of injection timing.
  if (typeof window !== 'undefined' && window.Telegram?.WebApp?.initData) {
    return window.Telegram.WebApp.initData
  }
  return twa?.initData ?? ''
}

/** Telegram user object from initData. */
export function getTelegramUser() {
  return twa?.initDataUnsafe?.user ?? null
}

/** Language code detected from the Telegram user profile. */
export function getLanguageCode(): string {
  return twa?.initDataUnsafe?.user?.language_code ?? 'it'
}

/** Whether we're actually running inside Telegram. */
export function isInsideTelegram(): boolean {
  return typeof window !== 'undefined'
    ? !!(window.Telegram?.WebApp?.initData || twa?.initData)
    : false
}

/**
 * Send a dice roll result back to the Telegram chat.
 * IMPORTANT: only works when the Mini App was opened via a reply keyboard button.
 * After calling this, the Mini App closes automatically.
 */
export function sendDiceResultToChat(result: {
  notation: string
  rolls: number[]
  total: number
}): void {
  if (!twa) return
  twa.sendData(
    JSON.stringify({ type: 'dice_roll', ...result })
  )
}

/** Signal to Telegram that the Mini App has finished loading. */
export function telegramReady(): void {
  // Read from window directly to avoid stale-capture of the `twa` constant.
  const webApp = typeof window !== 'undefined' ? window.Telegram?.WebApp : undefined
  webApp?.ready()
  webApp?.expand()
}

/** Show a native Telegram confirm dialog. */
export function telegramConfirm(
  message: string,
  callback: (confirmed: boolean) => void
): void {
  // Read WebApp dynamically: Telegram may inject it AFTER module init
  // (e.g. when the Mini App is opened via a reply keyboard button).
  const webApp =
    typeof window !== 'undefined' ? window.Telegram?.WebApp : undefined

  if (webApp && typeof webApp.showConfirm === 'function') {
    try {
      webApp.showConfirm(message, (confirmed) => {
        // Some Telegram clients invoke the callback with `undefined` when the
        // user dismisses via the back gesture — treat as "not confirmed".
        callback(!!confirmed)
      })
      return
    } catch {
      // Fall through to window.confirm if the native dialog errors out.
    }
  }
  callback(window.confirm(message))
}

/** Parametro startapp dei deep link (t.me/<bot>?startapp=…), se presente.
 *
 *  Telegram lo espone in `initDataUnsafe.start_param`, ma al LANCIO lo passa
 *  anche nel fragment dell'URL come `tgWebAppStartParam`
 *  (#tgWebAppData=…&tgWebAppStartParam=join_XXX). Leggiamo il fragment come
 *  fallback: è utile quando l'SDK non ha ancora popolato `initDataUnsafe` e,
 *  soprattutto, permette di risolvere il deep link prima che HashRouter monti
 *  (vedi main.tsx) — altrimenti il fragment è una "rotta" sconosciuta e la
 *  route `*` rimbalza su CharacterSelect. */
export function getStartParam(): string | null {
  const webApp = typeof window !== 'undefined' ? window.Telegram?.WebApp : undefined
  const fromSdk = webApp?.initDataUnsafe?.start_param ?? twa?.initDataUnsafe?.start_param
  if (fromSdk) return fromSdk
  if (typeof window !== 'undefined') {
    // Solo se il fragment è in forma key=value (lancio Telegram), non una
    // rotta applicativa `#/...` già normalizzata da HashRouter.
    const frag = window.location.hash.replace(/^#/, '')
    if (frag && !frag.startsWith('/')) {
      const fromHash = new URLSearchParams(frag).get('tgWebAppStartParam')
      if (fromHash) return fromHash
    }
    const fromSearch = new URLSearchParams(window.location.search).get('tgWebAppStartParam')
    if (fromSearch) return fromSearch
  }
  return null
}

/** Il client supporta la condivisione dei messaggi preparati (Bot API 8.0+)? */
export function canShareMessage(): boolean {
  const webApp = typeof window !== 'undefined' ? window.Telegram?.WebApp : undefined
  return !!webApp && typeof webApp.shareMessage === 'function'
}

/** Apre il picker nativo per condividere un messaggio preparato.
 *  Risolve a true se l'utente lo ha effettivamente inviato. */
export function shareTelegramMessage(msgId: string): Promise<boolean> {
  return new Promise((resolve) => {
    const webApp = typeof window !== 'undefined' ? window.Telegram?.WebApp : undefined
    if (!webApp || typeof webApp.shareMessage !== 'function') {
      resolve(false)
      return
    }
    try {
      webApp.shareMessage(msgId, (sent) => resolve(!!sent))
    } catch {
      resolve(false)
    }
  })
}

/** Haptic feedback helpers. */
export const haptic = {
  light: () => twa?.HapticFeedback.impactOccurred('light'),
  medium: () => twa?.HapticFeedback.impactOccurred('medium'),
  heavy: () => twa?.HapticFeedback.impactOccurred('heavy'),
  selection: () => twa?.HapticFeedback.selectionChanged(),
  success: () => twa?.HapticFeedback.notificationOccurred('success'),
  error: () => twa?.HapticFeedback.notificationOccurred('error'),
  warning: () => twa?.HapticFeedback.notificationOccurred('warning'),
}

export { twa as WebApp }

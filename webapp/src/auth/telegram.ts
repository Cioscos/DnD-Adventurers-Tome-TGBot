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
  }
  colorScheme: 'light' | 'dark'
  themeParams: Record<string, string>
  isExpanded: boolean
  viewportHeight: number
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
  ready(): void
  expand(): void
  close(): void
  sendData(data: string): void
  showAlert(message: string, callback?: () => void): void
  showConfirm(message: string, callback: (confirmed: boolean) => void): void
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
  return !!twa?.initData
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
  twa?.ready()
  twa?.expand()
}

/** Show a native Telegram confirm dialog. */
export function telegramConfirm(
  message: string,
  callback: (confirmed: boolean) => void
): void {
  if (twa) {
    twa.showConfirm(message, callback)
  } else {
    callback(window.confirm(message))
  }
}

/** Haptic feedback helpers. */
export const haptic = {
  light: () => twa?.HapticFeedback.impactOccurred('light'),
  success: () => twa?.HapticFeedback.notificationOccurred('success'),
  error: () => twa?.HapticFeedback.notificationOccurred('error'),
  warning: () => twa?.HapticFeedback.notificationOccurred('warning'),
}

export { twa as WebApp }

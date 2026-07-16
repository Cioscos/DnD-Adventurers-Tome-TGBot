import { haptic } from '@/auth/telegram'

export type HapticKind = 'light' | 'medium' | 'success' | 'error' | 'warning' | 'none'

/** Dispatch centralizzato dell'haptic Telegram usato dal kit UI (Button, IconButton, Pressable). */
export function fireHaptic(kind: HapticKind): void {
  if (kind === 'none') return
  if (kind === 'success') haptic.success()
  else if (kind === 'error') haptic.error()
  else if (kind === 'warning') haptic.warning()
  else if (kind === 'medium') haptic.medium()
  else haptic.light()
}

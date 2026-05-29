/**
 * Global surface for `homebrew_notifications` returned by backend mutations.
 *
 * Several API endpoints (PATCH /hp, POST /items/{id}/attack, PATCH
 * /conditions, POST /homebrew/turn-start, POST /homebrew/manual-trigger,
 * etc.) include an optional `homebrew_notifications` array on their
 * response body. Each entry describes a homebrew rule that fired during
 * the operation and what the player should know about it.
 *
 * This module exposes a single function — `showHomebrewNotifications` —
 * that dispatches each notification through the existing sonner toast
 * system. The function is plain (not a hook), so it can be invoked from
 * the global `MutationCache.onSuccess` callback wired in `main.tsx`.
 *
 * Wiring is global on purpose: every mutation response is inspected, so
 * future endpoints that add `homebrew_notifications` get UI coverage for
 * free without per-page changes.
 */

import { toast as sonnerToast } from 'sonner'
import { haptic } from '@/auth/telegram'

export type NotificationSeverity = 'info' | 'warning' | 'error' | 'success'

export interface NotificationLike {
  severity: NotificationSeverity
  message: string
  rule_id: number | null
  rule_name: string | null
}

/**
 * Dispatch a list of homebrew notifications through sonner.
 *
 * - Maps `severity` to the matching sonner variant.
 * - Uses `rule_name` (when present) as the toast `description` so the
 *   player can tell which rule fired.
 * - Errors get a longer 10s duration; other severities use sonner's
 *   default.
 * - Fires a single haptic at the start (matching the most severe entry
 *   in the batch — error > warning > success > info) instead of one per
 *   notification, to avoid vibration spam when a rule emits multiple.
 */
export function showHomebrewNotifications(list: NotificationLike[]): void {
  if (!Array.isArray(list) || list.length === 0) return

  // Single haptic, picked from the most attention-grabbing severity in
  // the batch so a chain of (info, info, error) still buzzes "error".
  const severities = list.map((n) => n.severity)
  if (severities.includes('error')) haptic.error()
  else if (severities.includes('warning')) haptic.warning()
  else if (severities.includes('success')) haptic.success()
  else haptic.light()

  for (const notif of list) {
    const description = notif.rule_name ?? undefined
    const opts: { description?: string; duration?: number } = { description }
    if (notif.severity === 'error') opts.duration = 10_000

    switch (notif.severity) {
      case 'success':
        sonnerToast.success(notif.message, opts)
        break
      case 'error':
        sonnerToast.error(notif.message, opts)
        break
      case 'warning':
        sonnerToast.warning(notif.message, opts)
        break
      case 'info':
      default:
        sonnerToast.info(notif.message, opts)
        break
    }
  }
}

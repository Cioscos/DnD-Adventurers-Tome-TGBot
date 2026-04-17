import { toast as sonnerToast } from 'sonner'
import { haptic } from '@/auth/telegram'

type ToastKind = 'success' | 'error' | 'info' | 'warning' | 'arcane' | 'default'

interface ToastOptions {
  description?: string
  duration?: number
  hapticFeedback?: boolean
}

/**
 * Unified toast helper — wraps sonner with Telegram haptic feedback.
 */
export function useToast() {
  const show = (kind: ToastKind, message: string, opts: ToastOptions = {}) => {
    const { description, duration, hapticFeedback = true } = opts
    if (hapticFeedback) {
      if (kind === 'success') haptic.success()
      else if (kind === 'error') haptic.error()
      else if (kind === 'warning') haptic.warning()
      else haptic.light()
    }
    const base = { description, duration }
    if (kind === 'success') sonnerToast.success(message, base)
    else if (kind === 'error') sonnerToast.error(message, base)
    else if (kind === 'warning') sonnerToast.warning(message, base)
    else if (kind === 'info') sonnerToast.info(message, base)
    else sonnerToast(message, base)
  }

  return {
    success: (m: string, o?: ToastOptions) => show('success', m, o),
    error: (m: string, o?: ToastOptions) => show('error', m, o),
    warning: (m: string, o?: ToastOptions) => show('warning', m, o),
    info: (m: string, o?: ToastOptions) => show('info', m, o),
    arcane: (m: string, o?: ToastOptions) => show('arcane', m, o),
    toast: (m: string, o?: ToastOptions) => show('default', m, o),
  }
}

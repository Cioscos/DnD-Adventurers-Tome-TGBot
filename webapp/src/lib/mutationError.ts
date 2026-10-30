import { toast } from 'sonner'
import { haptic } from '@/auth/telegram'
import i18n from '@/i18n'

/** Avviso standard per un'azione fallita: vibrazione + toast. È quello dell'handler
 *  globale in main.tsx; lo chiamano anche gli onError che fanno pulizia locale
 *  (un onError proprio esclude l'handler globale). */
export function notifyMutationError(): void {
  haptic.error()
  toast.error(i18n.t('common.action_failed'))
}

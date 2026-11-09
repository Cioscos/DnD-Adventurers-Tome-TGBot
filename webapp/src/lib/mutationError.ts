import { toast } from 'sonner'
import { haptic } from '@/auth/telegram'
import i18n from '@/i18n'
import { ApiError } from '@/api/client'

/** Avviso standard per un'azione fallita: vibrazione + toast. È quello dell'handler
 *  globale in main.tsx; lo chiamano anche gli onError che fanno pulizia locale
 *  (un onError proprio esclude l'handler globale). */
export function notifyMutationError(): void {
  haptic.error()
  toast.error(i18n.t('common.action_failed'))
}

const CAST_ERRORS = ['turn_slot_used', 'no_uses', 'pact_slot_required', 'surge_no_magic', 'invalid_target', 'target_dead', 'invalid_choice']

/** Un lancio rifiutato dal server per una regola (azione già spesa, usi finiti) lo dice con il suo testo; il resto è un errore generico. */
export function notifyCastError(err: unknown): void {
  const code = err instanceof ApiError ? (err.detail as { code?: string } | null)?.code : undefined
  if (code && CAST_ERRORS.includes(code)) {
    haptic.error()
    toast.error(i18n.t(`character.spells.roll_damage.cast_errors.${code}`))
  } else notifyMutationError()
}

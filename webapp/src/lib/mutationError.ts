import { toast } from 'sonner'
import { haptic } from '@/auth/telegram'
import i18n from '@/i18n'
import { ApiError } from '@/api/client'

/** Codici del server con un testo proprio (`common.server_errors.<codice>`) per i rifiuti che non hanno un messaggio di pagina. */
const SERVER_ERRORS = [
  'option_unavailable', 'turn_slot_used', 'no_uses', 'no_slot', 'target_not_down', 'nothing_to_remove', 'target_dead', 'invalid_target',
  'feature_unavailable', 'rest_needs_hp', 'long_rest_too_soon', 'state_locked',
  'no_stealth_roll', 'hide_failed', 'incapacitated', 'once_per_turn', 'replace_after_long_rest',
]

function errorCode(err: unknown): string | undefined {
  return err instanceof ApiError ? (err.detail as { code?: string } | null)?.code : undefined
}

/** Avviso standard per un'azione fallita: vibrazione + toast. È quello dell'handler
 *  globale in main.tsx; lo chiamano anche gli onError che fanno pulizia locale
 *  (un onError proprio esclude l'handler globale). Con l'errore dice il motivo che il server ha dato;
 *  «controlla la connessione» resta solo quando il server non ha risposto. */
export function notifyMutationError(err?: unknown): void {
  haptic.error()
  const code = errorCode(err)
  if (code && SERVER_ERRORS.includes(code)) toast.error(i18n.t(`common.server_errors.${code}`))
  else toast.error(i18n.t(err instanceof ApiError ? 'common.action_refused' : 'common.action_failed'))
}

const CAST_ERRORS = ['turn_slot_used', 'no_uses', 'pact_slot_required', 'surge_no_magic', 'invalid_target', 'target_dead', 'invalid_choice', 'option_unavailable']

/** Un lancio rifiutato dal server per una regola (azione già spesa, usi finiti) lo dice con il suo testo; il resto è un errore generico. */
export function notifyCastError(err: unknown): void {
  const code = errorCode(err)
  if (code && CAST_ERRORS.includes(code)) {
    haptic.error()
    toast.error(i18n.t(`character.spells.roll_damage.cast_errors.${code}`))
  } else notifyMutationError(err)
}

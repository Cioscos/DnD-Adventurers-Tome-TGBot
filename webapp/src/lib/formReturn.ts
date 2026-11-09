import { ApiError } from '@/api/client'

/** Tornare alla forma normale costa l'azione bonus (Druido 2014): il server rifiuta con `turn_slot_used` se è già spesa. */
export const bonusSpentOnReturn = (err: unknown): boolean =>
  err instanceof ApiError && (err.detail as { code?: string } | null)?.code === 'turn_slot_used'

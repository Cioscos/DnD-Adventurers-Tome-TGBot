import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '@/api/client'
import { useToast } from '@/hooks/useToast'
import { haptic } from '@/auth/telegram'
import type { CharacterFull, CoinKey, SessionParticipant, TradeRequest } from '@/types'

export const COIN_ORDER: CoinKey[] = ['platinum', 'gold', 'electrum', 'silver', 'copper']
export const COIN_ABBR: Record<CoinKey, string> = { platinum: 'PP', gold: 'GP', electrum: 'EP', silver: 'SP', copper: 'CP' }

/** Destinatario «Deposito di gruppo» nel selettore «Dai a…» (nessun utente reale ha id 0). */
export const STASH_TARGET = 0

/** Iniziale del selettore: l'unico destinatario possibile è preselezionato. */
export const initialTarget = (partners: SessionParticipant[], stash?: boolean): number | null =>
  partners.length === 1 && !stash ? partners[0].user_id : partners.length === 0 && stash ? STASH_TARGET : null

/** Mutazione di scambio: aggiorna la cache come «Sposta» e traduce gli errori API (403/409/410/422). */
export function useTradeMutation(charId: number, sessionId: number, onDone: () => void) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: ({ to_user_id, ...rest }: TradeRequest) =>
      to_user_id === STASH_TARGET ? api.sessions.stashPut(sessionId, rest) : api.sessions.trade(sessionId, { to_user_id, ...rest }),
    onSuccess: (updated: CharacterFull) => {
      qc.setQueryData(['character', charId], updated)
      qc.invalidateQueries({ queryKey: ['session-stash', sessionId] })
      const names = updated.unequipped_item_names ?? []
      if (names.length > 0) toast.info(t('character.inventory.containers.unequipped', { names: names.join(', ') }))
      haptic.success()
      onDone()
    },
    onError: (e) => {
      const detail = e instanceof ApiError && typeof e.detail === 'string' ? e.detail : ''
      const key = e instanceof ApiError && e.status === 410 ? 'closed' : detail
      toast.error(t(`character.inventory.give.errors.${key}`, { defaultValue: t('common.action_failed') }))
    },
  })
}

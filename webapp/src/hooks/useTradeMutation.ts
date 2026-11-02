import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '@/api/client'
import { useToast } from '@/hooks/useToast'
import { haptic } from '@/auth/telegram'
import type { CharacterFull, CoinKey, TradeRequest } from '@/types'

export const COIN_ORDER: CoinKey[] = ['platinum', 'gold', 'electrum', 'silver', 'copper']
export const COIN_ABBR: Record<CoinKey, string> = { platinum: 'PP', gold: 'GP', electrum: 'EP', silver: 'SP', copper: 'CP' }

/** Mutazione di scambio: aggiorna la cache come «Sposta» e traduce gli errori API (403/409/410/422). */
export function useTradeMutation(charId: number, sessionId: number, onDone: () => void) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: (body: TradeRequest) => api.sessions.trade(sessionId, body),
    onSuccess: (updated: CharacterFull) => {
      qc.setQueryData(['character', charId], updated)
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

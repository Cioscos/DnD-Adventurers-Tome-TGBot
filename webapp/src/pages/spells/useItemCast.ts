import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, ApiError } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { useToast } from '@/hooks/useToast'

/** Lancio di un incantesimo concesso da un oggetto: niente slot, il BE scala le cariche. */
export function useItemCast(charId: number) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: ({ itemId, spellIndex }: { itemId: number; spellIndex: number; name: string }) =>
      api.items.cast(charId, itemId, spellIndex),
    onSuccess: (updated, { name }) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
      toast.success(t('character.inventory.magic.cast_done', { name }))
    },
    onError: (err) => {
      const detail = err instanceof ApiError && err.status === 409 ? String(err.detail) : ''
      if (detail === 'not_enough_charges') toast.error(t('character.inventory.magic.not_enough_charges'))
      else if (detail === 'attunement_required') toast.error(t('character.inventory.magic.attunement_required'))
      else toast.error(t('common.action_failed'))
    },
  })
}

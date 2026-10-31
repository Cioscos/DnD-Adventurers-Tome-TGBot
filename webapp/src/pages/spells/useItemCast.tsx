import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, ApiError } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { useToast } from '@/hooks/useToast'
import { resolveItemCast, type ResolvedItemCast } from '@/lib/itemCast'
import ItemCastSheet from '@/pages/spells/ItemCastSheet'

/** Lancio di un incantesimo concesso da un oggetto: niente slot, il BE scala le cariche. */
export function useItemCast(charId: number) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [resolved, setResolved] = useState<ResolvedItemCast | null>(null)

  const mutation = useMutation({
    mutationFn: ({ itemId, spellIndex }: { itemId: number; spellIndex: number; name: string }) =>
      api.items.cast(charId, itemId, spellIndex),
    onSuccess: (updated, { itemId, spellIndex }) => {
      qc.setQueryData(['character', charId], updated)
      haptic.success()
      const item = updated.items?.find((i) => i.id === itemId)
      setResolved(item ? resolveItemCast(updated, item, spellIndex) : null)
    },
    onError: (err) => {
      const detail = err instanceof ApiError && err.status === 409 ? String(err.detail) : ''
      if (detail === 'no_charges') toast.error(t('character.inventory.magic.no_charges'))
      else if (detail === 'not_enough_charges') toast.error(t('character.inventory.magic.not_enough_charges'))
      else if (detail === 'attunement_required') toast.error(t('character.inventory.magic.attunement_required'))
      else toast.error(t('common.action_failed'))
    },
  })

  return {
    mutate: mutation.mutate,
    isPending: mutation.isPending,
    variables: mutation.variables,
    elements: resolved && (
      <ItemCastSheet charId={charId} resolved={resolved} onClose={() => setResolved(null)} />
    ),
  }
}

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { useToast } from '@/hooks/useToast'

/** "Fine round (−1)": scala le durate in round e avvisa degli effetti scaduti. */
export function useTickRound(charId: number) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: () => api.characters.tickRound(charId),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], updated)
      const expired = updated.expired_effects ?? []
      if (expired.length > 0) toast.info(t('character.conditions.duration.expired', { names: expired.join(', ') }))
      haptic.success()
    },
    onError: () => haptic.error(),
  })
}

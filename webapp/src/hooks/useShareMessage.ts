import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { haptic, shareTelegramMessage } from '@/auth/telegram'
import { useToast } from '@/hooks/useToast'

/** Prepara un messaggio lato API e apre il picker nativo di Telegram.
 *  `sent` è false se l'utente annulla il picker (nessun toast in quel caso). */
export function useShareMessage<TVars = void>(
  prepare: (vars: TVars) => Promise<{ prepared_message_id: string }>,
) {
  const toast = useToast()
  const { t } = useTranslation()
  return useMutation({
    mutationFn: async (vars: TVars) => {
      const { prepared_message_id } = await prepare(vars)
      return shareTelegramMessage(prepared_message_id)
    },
    onSuccess: (sent) => {
      if (sent) haptic.success()
    },
    onError: () => {
      haptic.error()
      toast.error(t('share.error'))
    },
  })
}

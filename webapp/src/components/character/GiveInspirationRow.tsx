import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import { PartnerPicker } from '@/pages/inventory/GiveSheet'
import { api, ApiError } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { useToast } from '@/hooks/useToast'
import { useTradePartners } from '@/hooks/useTradePartners'
import type { CharacterFull } from '@/types'

/** Ispirazione Eroica 2024: se ne ha una sola; chi l'ha già la può cedere a un compagno di sessione che ne è privo. */
export default function GiveInspirationRow({ char }: { char: CharacterFull }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const trade = useTradePartners(char.id)
  const [open, setOpen] = useState(false)
  const [to, setTo] = useState<number | null>(null)
  const give = useMutation({
    mutationFn: () => api.sessions.giveInspiration(trade!.sessionId, { from_character_id: char.id, to_user_id: to! }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', char.id], updated)
      haptic.success()
      setOpen(false)
    },
    onError: (e) => {
      const code = e instanceof ApiError && typeof e.detail === 'object' && e.detail ? (e.detail as { code?: string }).code : undefined
      toast.error(t(`character.inspiration.give_errors.${code ?? 'generic'}`, { defaultValue: t('common.action_failed') }))
    },
  })

  if (char.rules_edition !== '2024' || !char.heroic_inspiration || !trade || trade.partners.length === 0) return null
  return (
    <>
      <Button size="sm" variant="secondary" onClick={() => { setTo(trade.partners.length === 1 ? trade.partners[0].user_id : null); setOpen(true) }}>
        {t('character.inspiration.give')}
      </Button>
      {open && (
        <Sheet open onClose={() => setOpen(false)} title={t('character.inspiration.give')}>
          <div className="p-5 space-y-3">
            <p className="text-sm text-dnd-text-muted font-body">{t('character.inspiration.give_hint')}</p>
            <PartnerPicker partners={trade.partners} value={to} onChange={setTo} />
            <div className="flex gap-2 pt-1">
              <Button variant="secondary" fullWidth onClick={() => setOpen(false)}>{t('common.cancel')}</Button>
              <Button variant="primary" fullWidth disabled={to == null} loading={give.isPending} onClick={() => give.mutate()}>
                {t('character.inspiration.give_confirm')}
              </Button>
            </div>
          </div>
        </Sheet>
      )}
    </>
  )
}

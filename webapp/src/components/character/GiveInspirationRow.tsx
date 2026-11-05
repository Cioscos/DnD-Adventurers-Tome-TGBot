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

/** Ispirazione Eroica 2024: se ne ha una sola. Quando ne arriva un'altra a chi ce l'ha già, quella in più si cede a un
 *  compagno di sessione che ne è privo (o si perde); chi cede tiene la propria. */
export default function GiveInspirationRow({ char }: { char: CharacterFull }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const trade = useTradePartners(char.id)
  const [open, setOpen] = useState(false)
  const [to, setTo] = useState<number | null>(null)
  const partners = trade?.partners ?? []

  const openSheet = () => { setTo(partners.length === 1 ? partners[0].user_id : null); setOpen(true) }
  // Il percorso che concede: il server segna l'Ispirazione in più, la risposta dice che c'è qualcosa da cedere.
  const receive = useMutation({
    mutationFn: () => api.characters.updateInspiration(char.id, true),
    onSuccess: (updated) => {
      qc.setQueryData(['character', char.id], updated)
      if (updated.inspiration_extra) openSheet()
    },
  })
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

  if (char.rules_edition !== '2024' || !char.heroic_inspiration || partners.length === 0) return null
  return (
    <>
      <Button size="sm" variant="secondary" loading={receive.isPending}
        onClick={() => (char.inspiration_extra ? openSheet() : receive.mutate())}>
        {t(char.inspiration_extra ? 'character.inspiration.give' : 'character.inspiration.received_another')}
      </Button>
      {open && (
        <Sheet open onClose={() => setOpen(false)} title={t('character.inspiration.give')}>
          <div className="p-5 space-y-3">
            <p className="text-sm text-dnd-text-muted font-body">{t('character.inspiration.give_hint')}</p>
            <PartnerPicker partners={partners} value={to} onChange={setTo} />
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

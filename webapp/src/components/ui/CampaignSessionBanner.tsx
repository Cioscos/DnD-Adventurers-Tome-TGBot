import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Button from '@/components/ui/Button'
import JoinCampaignSessionSheet from '@/pages/campaign/JoinCampaignSessionSheet'
import type { ActiveCampaignSession } from '@/types'

/** Una riga per ogni sessione di campagna aperta a cui posso unirmi; niente se non ce ne sono. */
export default function CampaignSessionBanner() {
  const { t } = useTranslation()
  const [open, setOpen] = useState<ActiveCampaignSession | null>(null)
  // Niente polling per chi non ha campagne (la maggioranza).
  const { data: mine = [] } = useQuery({ queryKey: ['campaigns'], queryFn: () => api.campaigns.list() })
  const { data = [] } = useQuery({
    queryKey: ['campaign-active-for-me'],
    queryFn: () => api.campaigns.activeForMe(),
    retry: false,
    // Il master può aprire la serata mentre sei sulla home: va rilevata.
    refetchInterval: mine.length > 0 ? 15_000 : false,
    enabled: mine.length > 0,
  })
  if (data.length === 0) return null

  return (
    <>
      {data.map((it) => (
        <div
          key={it.session_id}
          className="flex items-center gap-3 px-3 py-2 rounded-lg border border-dnd-amber/60 bg-dnd-amber/10"
        >
          <div className="flex-1 min-w-0">
            <p className="text-sm font-display font-bold text-dnd-gold-bright truncate">{it.campaign_name}</p>
            <p className="text-xs font-cinzel uppercase tracking-widest text-dnd-amber">{t('campaign.session_open')}</p>
          </div>
          <Button variant="primary" size="md" onClick={() => setOpen(it)}>
            {t('campaign.enter')}
          </Button>
        </div>
      ))}
      {open && <JoinCampaignSessionSheet open onClose={() => setOpen(null)} item={open} />}
    </>
  )
}

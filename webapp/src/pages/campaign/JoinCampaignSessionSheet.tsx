import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import Skeleton from '@/components/ui/Skeleton'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { useToast } from '@/hooks/useToast'
import type { ActiveCampaignSession } from '@/types'

interface Props {
  open: boolean
  onClose: () => void
  item: ActiveCampaignSession
}

/** «Chi gioca stasera?»: sceglie il PG (non morto) con cui entrare nella sessione aperta. */
export default function JoinCampaignSessionSheet({ open, onClose, item }: Props) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [picked, setPicked] = useState<number | null>(null)

  const { data: camp, isLoading } = useQuery({
    queryKey: ['campaign', item.campaign_id],
    queryFn: () => api.campaigns.get(item.campaign_id),
    enabled: open,
  })
  const mine = (camp?.members ?? []).filter((m) => m.is_mine && m.status !== 'dead')
  const last = mine.find((m) => m.character_id === item.my_last_character_id)
  const charId = picked ?? last?.character_id ?? mine[0]?.character_id ?? null

  const join = useMutation({
    mutationFn: () => api.campaigns.joinSession(item.campaign_id, charId as number),
    onSuccess: (session) => {
      qc.setQueryData(['session-me'], session)
      haptic.success()
      navigate(`/session/${session.id}`, { replace: true })
    },
    onError: () => toast.error(t('common.action_failed')),
  })

  return (
    <Sheet open={open} onClose={onClose} title={t('campaign.who_plays')}>
      <div className="space-y-3 px-4 pb-4">
        {isLoading ? (
          <Skeleton.Rect height="64px" />
        ) : mine.length === 0 ? (
          <p className="text-sm text-dnd-text-muted font-body italic">{t('campaign.no_playable')}</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {mine.map((m) => (
              <Pressable
                key={m.character_id}
                onClick={() => setPicked(m.character_id)}
                className={`min-h-[44px] px-4 rounded-full border text-sm font-display font-bold max-w-full break-words
                  ${charId === m.character_id
                    ? 'bg-gradient-gold text-dnd-ink border-dnd-gold shadow-engrave'
                    : 'bg-dnd-surface border-dnd-border text-dnd-text'}`}
              >
                {m.character_name}
              </Pressable>
            ))}
          </div>
        )}
        <Button
          variant="primary"
          size="lg"
          fullWidth
          disabled={charId === null}
          loading={join.isPending}
          onClick={() => join.mutate()}
        >
          {t('campaign.enter')}
        </Button>
      </div>
    </Sheet>
  )
}

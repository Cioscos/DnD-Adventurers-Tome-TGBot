import { actionFailedKey } from '@/lib/mutationError'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import Skeleton from '@/components/ui/Skeleton'
import { api, ApiError } from '@/api/client'
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
      qc.invalidateQueries({ queryKey: ['campaign-active-for-me'] })
      haptic.success()
      navigate(`/session/${session.id}`, { replace: true })
    },
    onError: (err) => {
      const d = err instanceof ApiError && typeof err.detail === 'string' ? err.detail : ''
      const key = err instanceof ApiError && err.status === 409 ? 'session.already_in_other'
        : d === 'character_dead' ? 'campaign.join_err_dead'
        : d === 'no_active_session' ? 'campaign.join_err_no_session'
        : actionFailedKey(err)
      toast.error(t(key))
      if (d === 'no_active_session') qc.invalidateQueries({ queryKey: ['campaign-active-for-me'] })
    },
  })

  return (
    <Sheet open={open} onClose={onClose} title={t('campaign.who_plays')}>
      <div className="space-y-3 px-4 pb-4">
        <p className="text-sm text-dnd-text-muted font-body break-words">{item.campaign_name}</p>
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
                    ? 'bg-dnd-gold/20 text-dnd-gold-bright border-dnd-gold'
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

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

interface EnrollSheetProps {
  open: boolean
  onClose: () => void
  /** Codice campagna (8 caratteri, già maiuscolo). */
  code: string
}

const ERROR_KEYS: Record<string, string> = {
  already_in_campaign: 'campaign.enroll_err_already',
  gm_cannot_enroll: 'campaign.enroll_err_gm',
  campaign_not_found: 'campaign.enroll_err_not_found',
}

/** Iscrizione di un PG a una campagna. Non esiste un endpoint "PG già in campagna":
 *  si offrono tutti i propri PG e un 409 already_in_campaign diventa un toast. */
export default function EnrollSheet({ open, onClose, code }: EnrollSheetProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const toast = useToast()
  const qc = useQueryClient()
  const [charId, setCharId] = useState<number | null>(null)

  const { data: characters = [], isLoading } = useQuery({
    queryKey: ['characters'],
    queryFn: () => api.characters.list(),
    enabled: open,
  })

  const enroll = useMutation({
    mutationFn: () => api.campaigns.enroll(code, charId as number),
    onSuccess: (camp) => {
      haptic.success()
      qc.invalidateQueries({ queryKey: ['campaign-active-for-me'] })
      qc.invalidateQueries({ queryKey: ['campaigns'] })
      navigate(`/campaign/${camp.id}`, { replace: true })
    },
    onError: (err) => {
      const key = err instanceof ApiError && typeof err.detail === 'string' ? ERROR_KEYS[err.detail] : undefined
      toast.error(t(key ?? 'common.action_failed'))
    },
  })

  return (
    <Sheet open={open} onClose={onClose} title={t('campaign.enroll_title')}>
      <div className="space-y-3 px-4 pb-4">
        <p className="text-sm text-dnd-text-muted font-body">{t('campaign.enroll_pick')}</p>
        {isLoading ? (
          <Skeleton.Rect height="96px" />
        ) : characters.length === 0 ? (
          <div className="space-y-3">
            <p className="text-sm text-dnd-text-muted font-body italic">{t('campaign.enroll_no_characters')}</p>
            <Button variant="secondary" fullWidth onClick={() => navigate('/')}>
              {t('campaign.enroll_create')}
            </Button>
          </div>
        ) : (
          <div className="space-y-2">
            {characters.map((c) => (
              <Pressable
                key={c.id}
                onClick={() => setCharId(c.id)}
                className={`w-full text-left px-3 py-2.5 rounded-lg border transition-colors min-h-[44px]
                  ${charId === c.id
                    ? 'bg-gradient-gold text-dnd-ink border-dnd-gold shadow-engrave'
                    : 'bg-dnd-surface border-dnd-border text-dnd-text hover:border-dnd-gold-dim'}`}
              >
                <div className="flex max-xs:flex-col max-xs:items-start items-center justify-between gap-x-3 gap-y-0.5">
                  <span className="min-w-0 break-words font-display font-bold">{c.name}</span>
                  <span className="shrink-0 max-w-[50%] max-xs:max-w-full text-right max-xs:text-left text-xs opacity-80 font-body">
                    {c.class_summary}
                  </span>
                </div>
              </Pressable>
            ))}
          </div>
        )}
        {characters.length > 0 && (
        <Button
          variant="primary"
          size="lg"
          fullWidth
          disabled={charId === null}
          loading={enroll.isPending}
          onClick={() => enroll.mutate()}
        >
          {t('campaign.enroll_confirm')}
        </Button>
        )}
      </div>
    </Sheet>
  )
}

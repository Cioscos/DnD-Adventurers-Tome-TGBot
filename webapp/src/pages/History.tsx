import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import DndButton from '@/components/DndButton'
import ScrollArea from '@/components/ScrollArea'
import Skeleton from '@/components/Skeleton'
import { haptic } from '@/auth/telegram'

export default function History() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [confirmClear, setConfirmClear] = useState(false)

  const { data: entries = [], isLoading } = useQuery({
    queryKey: ['history', charId],
    queryFn: () => api.history.get(charId),
  })

  const clearMutation = useMutation({
    mutationFn: () => api.history.clear(charId),
    onSuccess: () => {
      qc.setQueryData(['history', charId], [])
      setConfirmClear(false)
      haptic.success()
    },
  })

  const formatDate = (iso: string) => {
    const d = new Date(iso)
    return d.toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
  }

  const EVENT_EMOJIS: Record<string, string> = {
    hp_change: '❤️', rest: '😴', ac_change: '🛡️', level_change: '⚔️',
    spell_slot_change: '🔮', spell_change: '✨', bag_change: '🎒',
    currency_change: '💰', ability_change: '⚡', death_save: '💀',
    condition_change: '🌀', other: '📌',
  }

  return (
    <Layout title={t('character.history.title')} backTo={`/char/${charId}`} group="tools" page="history">
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex gap-3 px-4 py-3 rounded-xl bg-dnd-surface">
              <Skeleton.Circle width="28px" delay={i * 80} />
              <div className="flex-1 space-y-2">
                <Skeleton.Line width="80%" height="14px" delay={i * 80} />
                <Skeleton.Line width="40%" height="10px" delay={i * 80 + 50} />
              </div>
            </div>
          ))}
        </div>
      ) : entries.length === 0 ? (
        <Card>
          <p className="text-center text-dnd-text-secondary">{t('character.history.empty')}</p>
        </Card>
      ) : (
        <>
          <ScrollArea>
            <div className="space-y-2">
              {[...entries].reverse().map((entry) => (
                <div
                  key={entry.id}
                  className="flex gap-3 px-4 py-3 rounded-xl bg-dnd-surface"
                >
                  <span className="text-xl shrink-0 mt-0.5">
                    {EVENT_EMOJIS[entry.event_type] ?? '📌'}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm leading-snug">{entry.description}</p>
                    <p className="text-xs text-dnd-text-secondary mt-0.5">
                      {formatDate(entry.timestamp)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>

          {confirmClear ? (
            <Card>
              <p className="text-sm text-center mb-3">{t('character.history.clear_confirm')}</p>
              <div className="flex gap-2">
                <DndButton
                  variant="danger"
                  onClick={() => clearMutation.mutate()}
                  loading={clearMutation.isPending}
                  className="flex-1"
                >
                  {t('common.confirm')}
                </DndButton>
                <DndButton
                  variant="secondary"
                  onClick={() => setConfirmClear(false)}
                  className="flex-1"
                >
                  {t('common.cancel')}
                </DndButton>
              </div>
            </Card>
          ) : (
            <DndButton
              variant="danger"
              onClick={() => setConfirmClear(true)}
              className="w-full"
            >
              🗑️ {t('character.history.clear')}
            </DndButton>
          )}
        </>
      )}
    </Layout>
  )
}

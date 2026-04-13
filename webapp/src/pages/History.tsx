import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import { haptic } from '@/auth/telegram'

export default function History() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [confirmClear, setConfirmClear] = useState(false)

  const { data: entries = [] } = useQuery({
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
    <Layout title={t('character.history.title')} backTo={`/char/${charId}`}>
      {entries.length === 0 ? (
        <Card>
          <p className="text-center text-[var(--tg-theme-hint-color)]">{t('character.history.empty')}</p>
        </Card>
      ) : (
        <>
          <div className="space-y-2">
            {[...entries].reverse().map((entry) => (
              <div
                key={entry.id}
                className="flex gap-3 px-4 py-3 rounded-xl bg-[var(--tg-theme-secondary-bg-color)]"
              >
                <span className="text-xl shrink-0 mt-0.5">
                  {EVENT_EMOJIS[entry.event_type] ?? '📌'}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm leading-snug">{entry.description}</p>
                  <p className="text-xs text-[var(--tg-theme-hint-color)] mt-0.5">
                    {formatDate(entry.timestamp)}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {confirmClear ? (
            <Card>
              <p className="text-sm text-center mb-3">{t('character.history.clear_confirm')}</p>
              <div className="flex gap-2">
                <button
                  onClick={() => clearMutation.mutate()}
                  className="flex-1 py-2 rounded-xl bg-red-500/80 text-white font-medium"
                >
                  {t('common.confirm')}
                </button>
                <button
                  onClick={() => setConfirmClear(false)}
                  className="flex-1 py-2 rounded-xl bg-white/10 font-medium"
                >
                  {t('common.cancel')}
                </button>
              </div>
            </Card>
          ) : (
            <button
              onClick={() => setConfirmClear(true)}
              className="w-full py-3 rounded-2xl bg-red-500/20 text-red-400 font-medium"
            >
              🗑️ {t('character.history.clear')}
            </button>
          )}
        </>
      )}
    </Layout>
  )
}

import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import { haptic } from '@/auth/telegram'

const COINS = [
  { key: 'platinum', emoji: '⬜', ratio: 100 },
  { key: 'gold',     emoji: '🟡', ratio: 10 },
  { key: 'electrum', emoji: '🔵', ratio: 5 },
  { key: 'silver',   emoji: '⚪', ratio: 1 },
  { key: 'copper',   emoji: '🟤', ratio: 0.1 },
] as const

type CoinKey = typeof COINS[number]['key']

export default function Currency() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const [draft, setDraft] = useState<Record<CoinKey, string>>({
    platinum: '', gold: '', electrum: '', silver: '', copper: '',
  })

  useEffect(() => {
    if (char?.currency) {
      setDraft({
        platinum: String(char.currency.platinum),
        gold: String(char.currency.gold),
        electrum: String(char.currency.electrum),
        silver: String(char.currency.silver),
        copper: String(char.currency.copper),
      })
    }
  }, [char?.currency?.id])

  const mutation = useMutation({
    mutationFn: () =>
      api.currency.update(charId, {
        platinum: Number(draft.platinum) || 0,
        gold: Number(draft.gold) || 0,
        electrum: Number(draft.electrum) || 0,
        silver: Number(draft.silver) || 0,
        copper: Number(draft.copper) || 0,
      }),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], (old: typeof char) =>
        old ? { ...old, currency: updated } : old
      )
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  if (!char) return null

  const totalGold = (
    (Number(draft.platinum) || 0) * 10 +
    (Number(draft.gold) || 0) +
    (Number(draft.electrum) || 0) * 0.5 +
    (Number(draft.silver) || 0) * 0.1 +
    (Number(draft.copper) || 0) * 0.01
  ).toFixed(2)

  return (
    <Layout title={t('character.currency.title')} backTo={`/char/${charId}`}>
      <Card>
        <p className="text-sm text-[var(--tg-theme-hint-color)] mb-1">{t('character.currency.total_gold')}</p>
        <p className="text-3xl font-bold text-yellow-400">🟡 {totalGold}</p>
      </Card>

      <div className="space-y-2">
        {COINS.map(({ key, emoji }) => (
          <Card key={key}>
            <div className="flex items-center gap-3">
              <span className="text-2xl">{emoji}</span>
              <span className="flex-1 font-medium">{t(`character.currency.${key}`)}</span>
              <input
                type="number"
                min="0"
                value={draft[key]}
                onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
                className="w-28 bg-white/10 rounded-xl px-3 py-2 text-lg font-bold text-center
                           outline-none focus:ring-2 focus:ring-[var(--tg-theme-button-color)]"
              />
            </div>
          </Card>
        ))}
      </div>

      <button
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
        className="w-full py-3 rounded-2xl bg-[var(--tg-theme-button-color)]
                   text-[var(--tg-theme-button-text-color)] font-semibold
                   disabled:opacity-40 active:opacity-80"
      >
        {mutation.isPending ? '...' : t('common.save')}
      </button>
    </Layout>
  )
}

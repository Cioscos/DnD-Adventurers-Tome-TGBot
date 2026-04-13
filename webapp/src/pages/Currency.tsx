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

  const [mode, setMode] = useState<'set' | 'add'>('set')
  const [draft, setDraft] = useState<Record<CoinKey, string>>({
    platinum: '', gold: '', electrum: '', silver: '', copper: '',
  })

  // Conversion state
  const [showConvert, setShowConvert] = useState(false)
  const [convertSource, setConvertSource] = useState<CoinKey>('gold')
  const [convertTarget, setConvertTarget] = useState<CoinKey>('silver')
  const [convertAmount, setConvertAmount] = useState('')

  useEffect(() => {
    if (char?.currency && mode === 'set') {
      setDraft({
        platinum: String(char.currency.platinum),
        gold: String(char.currency.gold),
        electrum: String(char.currency.electrum),
        silver: String(char.currency.silver),
        copper: String(char.currency.copper),
      })
    }
  }, [char?.currency?.id, mode])

  // When switching to 'add' mode, reset drafts to 0
  useEffect(() => {
    if (mode === 'add') {
      setDraft({ platinum: '0', gold: '0', electrum: '0', silver: '0', copper: '0' })
    } else if (char?.currency) {
      setDraft({
        platinum: String(char.currency.platinum),
        gold: String(char.currency.gold),
        electrum: String(char.currency.electrum),
        silver: String(char.currency.silver),
        copper: String(char.currency.copper),
      })
    }
  }, [mode])

  const mutation = useMutation({
    mutationFn: () => {
      const data: Record<string, number> = {}
      for (const { key } of COINS) {
        if (mode === 'add') {
          const current = char?.currency?.[key] ?? 0
          data[key] = Math.max(0, current + (Number(draft[key]) || 0))
        } else {
          data[key] = Number(draft[key]) || 0
        }
      }
      return api.currency.update(charId, data)
    },
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], (old: typeof char) =>
        old ? { ...old, currency: updated } : old
      )
      if (mode === 'add') {
        setDraft({ platinum: '0', gold: '0', electrum: '0', silver: '0', copper: '0' })
      }
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const convertMutation = useMutation({
    mutationFn: () =>
      api.currency.convert(charId, convertSource, convertTarget, Number(convertAmount) || 0),
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], (old: typeof char) =>
        old ? { ...old, currency: updated } : old
      )
      setConvertAmount('')
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  if (!char) return null

  const currentCoins = char.currency
  const totalGold = mode === 'set'
    ? (
      (Number(draft.platinum) || 0) * 10 +
      (Number(draft.gold) || 0) +
      (Number(draft.electrum) || 0) * 0.5 +
      (Number(draft.silver) || 0) * 0.1 +
      (Number(draft.copper) || 0) * 0.01
    ).toFixed(2)
    : (
      ((currentCoins?.platinum ?? 0) + (Number(draft.platinum) || 0)) * 10 +
      ((currentCoins?.gold ?? 0) + (Number(draft.gold) || 0)) +
      ((currentCoins?.electrum ?? 0) + (Number(draft.electrum) || 0)) * 0.5 +
      ((currentCoins?.silver ?? 0) + (Number(draft.silver) || 0)) * 0.1 +
      ((currentCoins?.copper ?? 0) + (Number(draft.copper) || 0)) * 0.01
    ).toFixed(2)

  return (
    <Layout title={t('character.currency.title')} backTo={`/char/${charId}`}>
      <Card>
        <p className="text-sm text-[var(--tg-theme-hint-color)] mb-1">{t('character.currency.total_gold')}</p>
        <p className="text-3xl font-bold text-yellow-400">🟡 {totalGold}</p>
      </Card>

      {/* Mode toggle */}
      <div className="flex gap-1 rounded-xl bg-[var(--tg-theme-secondary-bg-color)] p-1">
        <button
          onClick={() => setMode('set')}
          className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
            mode === 'set'
              ? 'bg-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-text-color)]'
              : 'text-[var(--tg-theme-hint-color)]'
          }`}
        >
          {t('character.currency.mode_set')}
        </button>
        <button
          onClick={() => setMode('add')}
          className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
            mode === 'add'
              ? 'bg-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-text-color)]'
              : 'text-[var(--tg-theme-hint-color)]'
          }`}
        >
          {t('character.currency.mode_add')}
        </button>
      </div>

      <div className="space-y-2">
        {COINS.map(({ key, emoji }) => (
          <Card key={key}>
            <div className="flex items-center gap-3">
              <span className="text-2xl">{emoji}</span>
              <div className="flex-1">
                <span className="font-medium">{t(`character.currency.${key}`)}</span>
                {mode === 'add' && currentCoins && (
                  <span className="text-xs text-[var(--tg-theme-hint-color)] ml-2">
                    ({currentCoins[key]})
                  </span>
                )}
              </div>
              <input
                type="number"
                min={mode === 'set' ? '0' : undefined}
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

      {/* Convert section */}
      <button
        onClick={() => setShowConvert(!showConvert)}
        className="w-full py-2.5 rounded-2xl bg-white/10 text-sm font-medium active:opacity-70"
      >
        🔄 {t('character.currency.convert')}
      </button>

      {showConvert && (
        <Card className="space-y-3">
          <div className="flex gap-2">
            <div className="flex-1">
              <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.currency.convert_from')}</p>
              <select
                value={convertSource}
                onChange={(e) => setConvertSource(e.target.value as CoinKey)}
                className="w-full bg-[var(--tg-theme-secondary-bg-color)] rounded-xl px-2 py-2 outline-none text-sm"
              >
                {COINS.map(({ key }) => (
                  <option key={key} value={key}>{t(`character.currency.${key}`)}</option>
                ))}
              </select>
            </div>
            <div className="flex items-end pb-2 text-[var(--tg-theme-hint-color)]">→</div>
            <div className="flex-1">
              <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.currency.convert_to')}</p>
              <select
                value={convertTarget}
                onChange={(e) => setConvertTarget(e.target.value as CoinKey)}
                className="w-full bg-[var(--tg-theme-secondary-bg-color)] rounded-xl px-2 py-2 outline-none text-sm"
              >
                {COINS.map(({ key }) => (
                  <option key={key} value={key}>{t(`character.currency.${key}`)}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <p className="text-xs text-[var(--tg-theme-hint-color)] mb-1">{t('character.currency.convert_amount')}</p>
            <input
              type="number"
              min="1"
              value={convertAmount}
              onChange={(e) => setConvertAmount(e.target.value)}
              placeholder="0"
              className="w-full bg-white/10 rounded-xl px-3 py-2 text-lg font-bold text-center
                         outline-none focus:ring-2 focus:ring-[var(--tg-theme-button-color)]"
            />
          </div>

          <button
            onClick={() => convertMutation.mutate()}
            disabled={convertMutation.isPending || !convertAmount || convertSource === convertTarget}
            className="w-full py-2.5 rounded-xl bg-[var(--tg-theme-button-color)]
                       text-[var(--tg-theme-button-text-color)] font-semibold
                       disabled:opacity-40 active:opacity-80"
          >
            {convertMutation.isPending ? '...' : t('character.currency.convert')}
          </button>
        </Card>
      )}
    </Layout>
  )
}

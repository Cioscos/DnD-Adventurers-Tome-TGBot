import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import DndInput from '@/components/DndInput'
import DndButton from '@/components/DndButton'
import { haptic } from '@/auth/telegram'
import { ArrowLeftRight } from 'lucide-react'

const COINS = [
  { key: 'platinum', emoji: '\u2B1C', ratio: 100 },
  { key: 'gold',     emoji: '\uD83D\uDFE1', ratio: 10 },
  { key: 'electrum', emoji: '\uD83D\uDD35', ratio: 5 },
  { key: 'silver',   emoji: '\u26AA', ratio: 1 },
  { key: 'copper',   emoji: '\uD83D\uDFE4', ratio: 0.1 },
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

  const currencyFingerprint = char?.currency
    ? `${char.currency.platinum}-${char.currency.gold}-${char.currency.electrum}-${char.currency.silver}-${char.currency.copper}`
    : null

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
  }, [currencyFingerprint, mode])

  // When switching to 'add' mode, reset drafts to 0
  useEffect(() => {
    if (mode === 'add') {
      setDraft({ platinum: '', gold: '', electrum: '', silver: '', copper: '' })
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
        setDraft({ platinum: '', gold: '', electrum: '', silver: '', copper: '' })
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
    <Layout title={t('character.currency.title')} backTo={`/char/${charId}`} group="equipment" page="currency">
      <Card variant="elevated">
        <p className="text-sm text-dnd-text-secondary mb-1">{t('character.currency.total_gold')}</p>
        <p className="text-3xl font-bold text-dnd-highlight">{'\uD83D\uDFE1'} {totalGold}</p>
      </Card>

      {/* Mode toggle */}
      <div className="flex gap-1 rounded-xl bg-dnd-surface p-1">
        <DndButton
          variant={mode === 'set' ? 'primary' : 'secondary'}
          onClick={() => setMode('set')}
          className="flex-1 !rounded-lg"
        >
          {t('character.currency.mode_set')}
        </DndButton>
        <DndButton
          variant={mode === 'add' ? 'primary' : 'secondary'}
          onClick={() => setMode('add')}
          className="flex-1 !rounded-lg"
        >
          {t('character.currency.mode_add')}
        </DndButton>
      </div>

      <div className="space-y-2">
        {COINS.map(({ key, emoji }) => (
          <Card key={key}>
            <div className="flex items-center gap-3">
              <span className="text-2xl">{emoji}</span>
              <div className="flex-1">
                <span className="font-medium">{t(`character.currency.${key}`)}</span>
                {mode === 'add' && currentCoins && (
                  <span className="text-xs text-dnd-text-secondary ml-2">
                    ({currentCoins[key]})
                  </span>
                )}
              </div>
              <DndInput
                type="number"
                min={mode === 'set' ? 0 : undefined}
                value={draft[key]}
                onChange={(v) => setDraft((d) => ({ ...d, [key]: v }))}
                placeholder="0"
                className="w-28"
              />
            </div>
          </Card>
        ))}
      </div>

      <DndButton
        onClick={() => mutation.mutate()}
        loading={mutation.isPending}
        className="w-full"
      >
        {t('common.save')}
      </DndButton>

      {/* Convert section */}
      <DndButton
        variant="secondary"
        onClick={() => setShowConvert(!showConvert)}
        className="w-full"
      >
        {'\uD83D\uDD04'} {t('character.currency.convert')}
      </DndButton>

      {showConvert && (
        <div
          className="fixed inset-0 bg-black/60 flex items-end z-50 p-4"
          onClick={() => setShowConvert(false)}
        >
          <Card className="w-full space-y-3" onClick={(e) => e.stopPropagation()}>
            <div className="flex gap-2">
              <div className="flex-1">
                <label className="block text-[11px] uppercase tracking-wider mb-1 font-medium text-dnd-gold-dim">
                  {t('character.currency.convert_from')}
                </label>
                <select
                  value={convertSource}
                  onChange={(e) => setConvertSource(e.target.value as CoinKey)}
                  className="w-full bg-dnd-surface rounded-xl px-2 py-3 min-h-[48px] outline-none text-sm text-dnd-text
                             border border-transparent focus:border-dnd-gold-dim"
                >
                  {COINS.map(({ key }) => (
                    <option key={key} value={key}>{t(`character.currency.${key}`)}</option>
                  ))}
                </select>
              </div>
              <button
                type="button"
                onClick={() => {
                  const tmp = convertSource
                  setConvertSource(convertTarget)
                  setConvertTarget(tmp)
                }}
                className="flex items-end pb-3 text-dnd-gold active:opacity-60 transition-opacity"
                aria-label={t('character.currency.swap')}
              >
                <ArrowLeftRight size={18} />
              </button>
              <div className="flex-1">
                <label className="block text-[11px] uppercase tracking-wider mb-1 font-medium text-dnd-gold-dim">
                  {t('character.currency.convert_to')}
                </label>
                <select
                  value={convertTarget}
                  onChange={(e) => setConvertTarget(e.target.value as CoinKey)}
                  className="w-full bg-dnd-surface rounded-xl px-2 py-3 min-h-[48px] outline-none text-sm text-dnd-text
                             border border-transparent focus:border-dnd-gold-dim"
                >
                  {COINS.map(({ key }) => (
                    <option key={key} value={key}>{t(`character.currency.${key}`)}</option>
                  ))}
                </select>
              </div>
            </div>

            <DndInput
              label={t('character.currency.convert_amount')}
              type="number"
              min={1}
              value={convertAmount}
              onChange={setConvertAmount}
              placeholder="0"
            />

            <DndButton
              onClick={() => convertMutation.mutate()}
              disabled={!convertAmount || convertSource === convertTarget}
              loading={convertMutation.isPending}
              className="w-full"
            >
              {t('character.currency.convert')}
            </DndButton>
          </Card>
        </div>
      )}
    </Layout>
  )
}

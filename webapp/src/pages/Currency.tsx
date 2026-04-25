import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { ArrowLeftRight, Save, RefreshCw } from 'lucide-react'
import { GiTwoCoins as Coins } from 'react-icons/gi'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import Sheet from '@/components/ui/Sheet'
import { haptic } from '@/auth/telegram'
import { spring } from '@/styles/motion'

const COINS = [
  { key: 'platinum', color: 'from-slate-200 via-slate-400 to-slate-500', label: 'PP' },
  { key: 'gold',     color: 'from-yellow-300 via-amber-500 to-yellow-700', label: 'GP' },
  { key: 'electrum', color: 'from-emerald-200 via-cyan-400 to-emerald-600', label: 'EP' },
  { key: 'silver',   color: 'from-zinc-200 via-zinc-400 to-zinc-500', label: 'SP' },
  { key: 'copper',   color: 'from-orange-300 via-orange-600 to-amber-900', label: 'CP' },
] as const

type CoinKey = typeof COINS[number]['key']

function CoinTile({ colorClass, label }: { colorClass: string; label: string }) {
  return (
    <div className={`w-11 h-11 rounded-full bg-gradient-to-br ${colorClass} border-2 border-dnd-gold-deep/60 flex items-center justify-center font-cinzel font-black text-[10px] shadow-parchment-md text-dnd-ink`}>
      {label}
    </div>
  )
}

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currencyFingerprint, mode])

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      setShowConvert(false)
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
      {/* Total gold hero */}
      <Surface variant="tome" ornamented className="text-center">
        <p className="text-[10px] font-cinzel uppercase tracking-[0.3em] text-dnd-gold-dim mb-1">
          {t('character.currency.total_gold')}
        </p>
        <div className="flex items-center justify-center gap-3">
          <Coins size={32} className="text-dnd-gold-bright drop-shadow-[0_0_8px_var(--dnd-gold-glow)]" />
          <m.span
            key={totalGold}
            initial={{ scale: 0.85, opacity: 0.5 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={spring.elastic}
            className="text-4xl font-display font-black text-dnd-gold-bright"
            style={{ textShadow: '0 2px 8px var(--dnd-gold-glow)' }}
          >
            {totalGold}
          </m.span>
        </div>
      </Surface>

      {/* Mode toggle */}
      <Surface variant="flat" className="!p-1.5">
        <div className="grid grid-cols-2 gap-1">
          {(['set', 'add'] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`min-h-[40px] rounded-lg font-cinzel text-xs uppercase tracking-widest transition-colors
                ${mode === m
                  ? 'bg-gradient-gold text-dnd-ink shadow-engrave'
                  : 'bg-transparent text-dnd-text-muted'}`}
            >
              {t(`character.currency.mode_${m}`)}
            </button>
          ))}
        </div>
      </Surface>

      {/* Coin rows */}
      <div className="space-y-2">
        {COINS.map(({ key, color, label }) => (
          <Surface key={key} variant="elevated">
            <div className="flex items-center gap-3">
              <CoinTile colorClass={color} label={label} />
              <div className="flex-1">
                <span className="font-display font-bold text-dnd-gold-bright">{t(`character.currency.${key}`)}</span>
                {mode === 'add' && currentCoins && (
                  <span className="text-xs text-dnd-text-faint ml-2 font-mono">
                    ({currentCoins[key]})
                  </span>
                )}
              </div>
              <Input
                type="number"
                min={mode === 'set' ? 0 : undefined}
                value={draft[key]}
                onChange={(v) => setDraft((d) => ({ ...d, [key]: v }))}
                placeholder="0"
                inputMode="numeric"
                className="w-24 [&_input]:text-center [&_input]:font-mono [&_input]:font-bold"
              />
            </div>
          </Surface>
        ))}
      </div>

      <Button
        variant="primary"
        size="lg"
        fullWidth
        onClick={() => mutation.mutate()}
        loading={mutation.isPending}
        icon={<Save size={18} />}
        haptic="success"
      >
        {t('common.save')}
      </Button>

      <Button
        variant="arcane"
        size="md"
        fullWidth
        onClick={() => setShowConvert(true)}
        icon={<RefreshCw size={16} />}
      >
        {t('character.currency.convert')}
      </Button>

      {/* Convert Sheet */}
      <Sheet open={showConvert} onClose={() => setShowConvert(false)} title={t('character.currency.convert')}>
        <div className="p-5 space-y-3">
          <div className="flex gap-2 items-center">
            <div className="flex-1">
              <label className="block text-[10px] uppercase tracking-widest mb-1.5 font-cinzel text-dnd-gold-dim">
                {t('character.currency.convert_from')}
              </label>
              <select
                value={convertSource}
                onChange={(e) => setConvertSource(e.target.value as CoinKey)}
                className="w-full px-3 py-2.5 min-h-[48px] rounded-lg bg-dnd-surface text-dnd-text
                           border-b-2 border-dnd-border outline-none font-body text-sm"
              >
                {COINS.map(({ key }) => (
                  <option key={key} value={key}>{t(`character.currency.${key}`)}</option>
                ))}
              </select>
            </div>
            <m.button
              type="button"
              onClick={() => {
                const tmp = convertSource
                setConvertSource(convertTarget)
                setConvertTarget(tmp)
              }}
              className="self-end mb-1 w-10 h-10 rounded-full bg-dnd-surface-raised border border-dnd-gold-dim/40 flex items-center justify-center text-dnd-gold-bright"
              whileTap={{ scale: 0.9, rotate: 180 }}
              aria-label={t('character.currency.swap')}
            >
              <ArrowLeftRight size={16} />
            </m.button>
            <div className="flex-1">
              <label className="block text-[10px] uppercase tracking-widest mb-1.5 font-cinzel text-dnd-gold-dim">
                {t('character.currency.convert_to')}
              </label>
              <select
                value={convertTarget}
                onChange={(e) => setConvertTarget(e.target.value as CoinKey)}
                className="w-full px-3 py-2.5 min-h-[48px] rounded-lg bg-dnd-surface text-dnd-text
                           border-b-2 border-dnd-border outline-none font-body text-sm"
              >
                {COINS.map(({ key }) => (
                  <option key={key} value={key}>{t(`character.currency.${key}`)}</option>
                ))}
              </select>
            </div>
          </div>

          <Input
            label={t('character.currency.convert_amount')}
            type="number"
            min={1}
            value={convertAmount}
            onChange={setConvertAmount}
            placeholder="0"
            inputMode="numeric"
          />

          <div className="flex gap-2 pt-1">
            <Button
              variant="primary"
              fullWidth
              onClick={() => convertMutation.mutate()}
              disabled={!convertAmount || convertSource === convertTarget}
              loading={convertMutation.isPending}
              haptic="success"
            >
              {t('character.currency.convert')}
            </Button>
            <Button variant="secondary" fullWidth onClick={() => setShowConvert(false)}>
              {t('common.cancel')}
            </Button>
          </div>
        </div>
      </Sheet>
    </Layout>
  )
}

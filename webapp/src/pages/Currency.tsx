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
  { key: 'platinum', metal: 'platinum', label: 'PP' },
  { key: 'gold',     metal: 'gold',     label: 'GP' },
  { key: 'electrum', metal: 'electrum', label: 'EP' },
  { key: 'silver',   metal: 'silver',   label: 'SP' },
  { key: 'copper',   metal: 'copper',   label: 'CP' },
] as const

// D&D 5e standard rates expressed in gold-piece equivalents (1 GP = 1.0).
const COIN_IN_GOLD: Record<string, number> = {
  platinum: 10,
  gold: 1,
  electrum: 0.5,
  silver: 0.1,
  copper: 0.01,
}

type CoinKey = typeof COINS[number]['key']
type CoinMetal = typeof COINS[number]['metal']

function CoinTile({ metal, label }: { metal: CoinMetal; label: string }) {
  const style = {
    background: `radial-gradient(circle at 32% 28%, var(--dnd-coin-${metal}-bright) 0%, var(--dnd-coin-${metal}) 55%, var(--dnd-coin-${metal}-deep) 100%)`,
  }
  return (
    <div
      className="w-11 h-11 rounded-full border-2 border-dnd-gold-deep/60 flex items-center justify-center font-cinzel font-black text-[10px] shadow-parchment-md text-dnd-ink"
      style={style}
    >
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

  const [mode, setMode] = useState<'set' | 'add'>('add')
  const [draft, setDraft] = useState<Record<CoinKey, string>>({
    platinum: '', gold: '', electrum: '', silver: '', copper: '',
  })

  const [showConvert, setShowConvert] = useState(false)
  const [convertSource, setConvertSource] = useState<CoinKey>('gold')
  const [convertTarget, setConvertTarget] = useState<CoinKey>('silver')
  const [convertAmount, setConvertAmount] = useState('')

  // Reset draft on mode switch — never pre-fill, current values shown as placeholder.
  useEffect(() => {
    setDraft({ platinum: '', gold: '', electrum: '', silver: '', copper: '' })
  }, [mode])

  const mutation = useMutation({
    mutationFn: () => {
      const data: Record<string, number> = {}
      for (const { key } of COINS) {
        const current = char?.currency?.[key] ?? 0
        if (mode === 'add') {
          data[key] = Math.max(0, current + (Number(draft[key]) || 0))
        } else {
          // 'set' mode: empty input → keep current value (placeholder hint).
          data[key] = draft[key] === '' ? current : Number(draft[key]) || 0
        }
      }
      return api.currency.update(charId, data)
    },
    onSuccess: (updated) => {
      qc.setQueryData(['character', charId], (old: typeof char) =>
        old ? { ...old, currency: updated } : old
      )
      setDraft({ platinum: '', gold: '', electrum: '', silver: '', copper: '' })
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

  const settings = (char.settings as Record<string, unknown>) ?? {}
  const hideElectrum = settings.hide_electrum === true
  const currentCoins = char.currency
  // Live total preview: in 'set' mode use draft (0 if empty); in 'add' mode add draft to current.
  const resolved = (key: CoinKey) => {
    const drafted = Number(draft[key]) || 0
    if (mode === 'set') return draft[key] === '' ? (currentCoins?.[key] ?? 0) : drafted
    return (currentCoins?.[key] ?? 0) + drafted
  }
  const totalGold = (
    resolved('platinum') * 10 +
    resolved('gold') +
    resolved('electrum') * 0.5 +
    resolved('silver') * 0.1 +
    resolved('copper') * 0.01
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
              className={`min-h-[44px] rounded-lg font-cinzel text-xs uppercase tracking-widest transition-colors
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
        {COINS.map(({ key, metal, label }) => {
          // Hide Electrum when the character has opted out via Settings.
          if (key === 'electrum' && hideElectrum) return null
          const draftNum = Number(draft[key]) || 0
          const isNegativeAdd = mode === 'add' && draftNum < 0
          return (
            <Surface key={key} variant="elevated">
              <div className="flex items-center gap-3">
                <CoinTile metal={metal} label={label} />
                <div className="flex-1 min-w-0">
                  <p className="font-display font-bold text-dnd-gold-bright">
                    {t(`character.currency.${key}`)}
                  </p>
                  {currentCoins && (
                    <p className="text-[10px] text-dnd-text-faint mt-0.5 font-mono">
                      {t('character.currency.current_value', { n: currentCoins[key] })}
                    </p>
                  )}
                  {isNegativeAdd && (
                    <p className="text-[10px] text-[var(--dnd-crimson-bright)] mt-0.5 font-body italic">
                      {t('character.currency.remove_preview', {
                        amount: Math.abs(draftNum),
                        coin: label,
                      })}
                    </p>
                  )}
                </div>
                <Input
                  type="number"
                  min={mode === 'set' ? 0 : undefined}
                  value={draft[key]}
                  onChange={(v) => setDraft((d) => ({ ...d, [key]: v }))}
                  placeholder={mode === 'add' ? '+/-' : String(currentCoins?.[key] ?? 0)}
                  inputMode="numeric"
                  className="w-24 [&_input]:text-center [&_input]:font-mono [&_input]:font-bold"
                />
              </div>
            </Surface>
          )
        })}
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
              className="self-end mb-1 w-11 h-11 rounded-full bg-dnd-surface-raised border border-dnd-gold-dim/40 flex items-center justify-center text-dnd-gold-bright"
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

          {convertAmount !== '' && convertSource !== convertTarget && (() => {
            const amountNum = Number(convertAmount) || 0
            const inGold = amountNum * (COIN_IN_GOLD[convertSource] ?? 0)
            const targetRate = COIN_IN_GOLD[convertTarget] ?? 1
            const targetAmount = inGold / targetRate
            return (
              <p className="text-[11px] font-body text-dnd-text-faint text-center">
                {t('character.currency.convert_preview', {
                  amount: amountNum,
                  source: t(`character.currency.${convertSource}`),
                  result: Number.isInteger(targetAmount) ? targetAmount : targetAmount.toFixed(2),
                  target: t(`character.currency.${convertTarget}`),
                  defaultValue: '{{amount}} {{source}} = {{result}} {{target}}',
                })}
              </p>
            )
          })()}

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

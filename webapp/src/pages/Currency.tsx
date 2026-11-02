import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m } from 'framer-motion'
import { ArrowUpDown, RefreshCw, Delete, Minus, Plus } from 'lucide-react'
import { GiTwoCoins as Coins } from 'react-icons/gi'
import { toast } from 'sonner'
import { api } from '@/api/client'
import type { Currency as CurrencyData } from '@/types'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import Sheet from '@/components/ui/Sheet'
import ChipSelect from '@/components/ui/ChipSelect'
import { showUndoToast } from '@/components/ui/UndoToast'
import { haptic } from '@/auth/telegram'
import { spring } from '@/styles/motion'
import CurrencySkeleton from '@/components/skeletons/CurrencySkeleton'
import { useIsFirstValue } from '@/hooks/useIsFirstValue'

const COINS = [
  { key: 'platinum', label: 'PP' },
  { key: 'gold',     label: 'GP' },
  { key: 'electrum', label: 'EP' },
  { key: 'silver',   label: 'SP' },
  { key: 'copper',   label: 'CP' },
] as const

type CoinKey = typeof COINS[number]['key']

// Valori in rame, come il modello del server (Currency.RATES): la conversione dà
// un intero della moneta di arrivo e il resto torna in rame.
const IN_COPPER: Record<CoinKey, number> = { platinum: 1000, gold: 100, electrum: 50, silver: 10, copper: 1 }
const MAX_DIGITS = 7

function CoinTile({ metal, label }: { metal: CoinKey; label: string }) {
  const style = {
    background: `radial-gradient(circle at 32% 28%, var(--dnd-coin-${metal}-bright) 0%, var(--dnd-coin-${metal}) 55%, var(--dnd-coin-${metal}-deep) 100%)`,
  }
  return (
    <span
      aria-hidden
      className={`w-8 h-8 text-xs shrink-0 rounded-full border-2 border-dnd-gold-deep/60 flex items-center justify-center font-cinzel font-black shadow-parchment-md text-dnd-ink`}
      style={style}
    >
      {label}
    </span>
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
  // Pop del valore solo quando CAMBIA, non all'ingresso nella pagina.
  const isFirstValue = useIsFirstValue(char)

  // Transazione: una moneta alla volta; le cifre miste sono due operazioni di seguito.
  const [coin, setCoin] = useState<CoinKey>('gold')
  const [digits, setDigits] = useState('')
  // Dopo una transazione la cifra resta (per ripeterla su un'altra moneta); la prossima cifra la sostituisce.
  const [fresh, setFresh] = useState(false)

  const [exactCoin, setExactCoin] = useState<CoinKey | null>(null)
  const [exactDraft, setExactDraft] = useState('')

  const [showConvert, setShowConvert] = useState(false)
  const [convertSource, setConvertSource] = useState<CoinKey>('gold')
  const [convertTarget, setConvertTarget] = useState<CoinKey>('silver')
  const [convertAmount, setConvertAmount] = useState('')

  const coinName = (k: CoinKey) => t(`character.currency.${k}`)
  const current = (k: CoinKey) => qc.getQueryData<{ currency?: CurrencyData }>(['character', charId])?.currency?.[k] ?? 0
  const setCached = (updated: Partial<CurrencyData>) =>
    qc.setQueryData(['character', charId], (old: typeof char) =>
      old ? { ...old, currency: { ...old.currency, ...updated } } : old,
    )

  // Salva subito il nuovo valore di UNA moneta (PATCH parziale: le altre restano come sono sul server).
  // Stesso scope = salvataggi e conversioni in fila: i PATCH a valore assoluto arrivano in ordine.
  const scope = { id: `currency-${charId}` }
  const saveCoin = useMutation({
    scope,
    mutationFn: ({ key, value }: { key: CoinKey; value: number }) =>
      api.currency.update(charId, { [key]: value }),
    onMutate: ({ key, value }) => setCached({ [key]: value }),
    // Una risposta vecchia non deve sovrascrivere il valore ottimistico di un'operazione ancora in coda.
    onSuccess: (updated) => { if (qc.isMutating({ predicate: (mu) => mu.options.scope?.id === scope.id }) <= 1) setCached(updated) },
    // Dopo un errore la cache non è affidabile (altre operazioni in coda): si rilegge dal server.
    onError: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      haptic.error()
      toast.error(t('character.currency.save_error'))
    },
  })

  const apply = (key: CoinKey, delta: number, undoable = true) => {
    const before = current(key)
    const value = Math.max(0, before + delta)
    saveCoin.mutate({ key, value })
    if (!undoable) return
    haptic.success()
    showUndoToast({
      message: t(delta < 0 ? 'character.currency.spent_toast' : 'character.currency.received_toast', {
        n: Math.abs(delta), coin: coinName(key),
      }),
      actionLabel: t('character.currency.undo'),
      // Inversa sul valore corrente: non cancella le transazioni fatte nel frattempo.
      onUndo: () => apply(key, before - value, false),
    })
  }

  const setExact = (key: CoinKey, value: number) => {
    const before = current(key)
    saveCoin.mutate({ key, value })
    haptic.success()
    showUndoToast({
      message: t('character.currency.set_toast', { n: value, coin: coinName(key) }),
      actionLabel: t('character.currency.undo'),
      // Inversa di questo cambio, non ritorno al valore di prima: tiene le operazioni fatte dopo.
      onUndo: () => apply(key, before - value, false),
    })
  }

  const convertMutation = useMutation({
    scope,
    mutationFn: () =>
      api.currency.convert(charId, convertSource, convertTarget, Math.floor(Number(convertAmount)) || 0),
    onSuccess: (updated) => {
      setCached(updated)
      setConvertAmount('')
      setShowConvert(false)
      haptic.success()
    },
    onError: () => {
      haptic.error()
      toast.error(t('character.currency.convert_error'))
    },
  })

  const amount = Number(digits) || 0
  const typeDigit = (d: string) => {
    haptic.light()
    const base = fresh ? '' : digits
    setFresh(false)
    setDigits((base + d).replace(/^0+/, '').slice(0, MAX_DIGITS))
  }
  const backspace = () => {
    haptic.light()
    setFresh(false)
    setDigits((v) => (fresh ? '' : v.slice(0, -1)))
  }
  const commit = (sign: 1 | -1) => {
    if (amount <= 0) return
    apply(coin, sign * amount)
    setFresh(true)
  }

  // Desktop: cifre e Backspace dalla tastiera fisica, se non si sta scrivendo in un campo.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null
      if (target?.closest('input, textarea, [contenteditable]') || exactCoin || showConvert) return
      if (/^[0-9]$/.test(e.key)) typeDigit(e.key)
      else if (e.key === 'Backspace') backspace()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  if (!char) {
    return (
      <Layout title={t('character.currency.title')} backTo={`/char/${charId}`} group="equipment" page="currency">
        <CurrencySkeleton />
      </Layout>
    )
  }

  const settings = (char.settings as Record<string, unknown>) ?? {}
  const coins = COINS.filter(({ key }) => !(key === 'electrum' && settings.hide_electrum === true))
  const have = (k: CoinKey) => char.currency?.[k] ?? 0
  const totalGold = (coins.reduce((sum, { key }) => sum + have(key) * IN_COPPER[key], 0) / 100).toFixed(2)
  const notEnough = amount > have(coin)

  const convertPreview = (() => {
    const n = Number(convertAmount) || 0
    if (n <= 0 || convertSource === convertTarget) return null
    const copper = n * IN_COPPER[convertSource]
    const result = Math.floor(copper / IN_COPPER[convertTarget])
    const rest = copper % IN_COPPER[convertTarget]
    const text = t('character.currency.convert_preview', {
      amount: n, source: coinName(convertSource), result, target: coinName(convertTarget),
    })
    return rest ? `${text} ${t('character.currency.convert_rest', { n: rest })}` : text
  })()

  return (
    <Layout title={t('character.currency.title')} backTo={`/char/${charId}`} group="equipment" page="currency">
      {/* Borsa: le monete in grande, toccandone una la imposti a un valore esatto. */}
      <Surface variant="tome" ornamented className="!p-3">
        <div className={`grid gap-1.5 ${coins.length === 5 ? 'grid-cols-5' : 'grid-cols-4'}`}>
          {coins.map(({ key, label }) => (
            <Pressable
              key={key}
              onClick={() => { haptic.light(); setExactDraft(''); setExactCoin(key) }}
              whileTap={{ scale: 0.95 }}
              aria-label={`${coinName(key)}: ${have(key)}`}
              className="min-h-[64px] min-w-0 flex flex-col items-center justify-center gap-1 rounded-xl bg-dnd-surface/60 border border-dnd-border hover:border-dnd-gold/60 transition-colors"
            >
              <CoinTile metal={key} label={label} />
              <span className="max-w-full truncate px-0.5 text-lg font-mono font-bold tabular-nums text-dnd-text leading-none">
                {have(key)}
              </span>
            </Pressable>
          ))}
        </div>
        <div className="mt-2 flex items-center gap-2">
          <Coins size={18} className="shrink-0 text-dnd-gold-bright" />
          {/* Etichetta sopra il numero: in riga col pulsante sforava a 360px con totali a 4+ cifre. */}
          <div className="min-w-0 flex-1">
            <p className="text-xs font-cinzel uppercase text-dnd-gold-dim truncate">
              {t('character.currency.total_gold')}
            </p>
            <m.p
              key={totalGold}
              initial={isFirstValue ? false : { scale: 0.85, opacity: 0.5 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={spring.elastic}
              className="origin-left text-xl font-display font-black tabular-nums text-dnd-gold-bright truncate"
            >
              {totalGold}
            </m.p>
          </div>
          {/* Conversione: azione neutra, non magica — secondary (Semantic Triad). */}
          <Button
            variant="secondary"
            size="sm"
            className="shrink-0"
            onClick={() => setShowConvert(true)}
            icon={<RefreshCw size={14} />}
          >
            {t('character.currency.convert')}
          </Button>
        </div>
      </Surface>

      {/* Transazione su una moneta */}
      <Surface variant="elevated" className="!p-3 space-y-2.5">
        <div className={`grid gap-1.5 ${coins.length === 5 ? 'grid-cols-5' : 'grid-cols-4'}`}>
          {coins.map(({ key, label }) => (
            <Pressable
              key={key}
              onClick={() => { haptic.light(); setCoin(key) }}
              aria-pressed={coin === key}
              className={`min-h-[44px] flex items-center justify-center gap-1.5 rounded-lg border font-cinzel font-bold text-sm transition-colors ${
                coin === key
                  ? 'bg-dnd-gold/20 border-dnd-gold text-dnd-gold-bright'
                  : 'bg-dnd-surface border-dnd-border text-dnd-text-muted'
              }`}
            >
              {label}
            </Pressable>
          ))}
        </div>

        <div className="flex items-baseline justify-end gap-2 px-2 min-h-[40px]">
          <span
            data-testid="tx-amount"
            className={`text-4xl font-mono font-bold tabular-nums leading-none ${
              fresh || amount === 0 ? 'text-dnd-text-faint' : 'text-dnd-text'
            }`}
          >
            {amount}
          </span>
          <span className="text-sm font-cinzel text-dnd-gold-dim">{coinName(coin)}</span>
        </div>
        <p className={`-mt-2 px-2 text-right text-xs font-body ${notEnough ? 'text-dnd-crimson-bright' : 'text-dnd-text-faint'}`}>
          {notEnough
            ? t('character.currency.not_enough', { n: have(coin), coin: coinName(coin) })
            : t('character.currency.you_have', { n: have(coin), coin: coinName(coin) })}
        </p>

        <div className="grid grid-cols-3 gap-1.5">
          {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((d) => (
            <Pressable
              key={d}
              onClick={() => typeDigit(d)}
              whileTap={{ scale: 0.94 }}
              className="min-h-[44px] rounded-xl bg-dnd-surface border border-dnd-border text-xl font-mono font-bold text-dnd-text"
            >
              {d}
            </Pressable>
          ))}
          <Pressable
            onClick={backspace}
            whileTap={{ scale: 0.94 }}
            aria-label={t('character.currency.backspace')}
            className="min-h-[44px] rounded-xl bg-dnd-surface border border-dnd-border flex items-center justify-center text-dnd-gold-dim"
          >
            <Delete size={20} />
          </Pressable>
          {['0', '00'].map((d) => (
            <Pressable
              key={d}
              onClick={() => typeDigit(d)}
              whileTap={{ scale: 0.94 }}
              className="min-h-[44px] rounded-xl bg-dnd-surface border border-dnd-border text-xl font-mono font-bold text-dnd-text"
            >
              {d}
            </Pressable>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-2">
          <Button
            variant="danger"
            size="md"
            onClick={() => commit(-1)}
            disabled={amount <= 0 || notEnough}
            icon={<Minus size={18} />}
            aria-label={t('character.currency.spend')}
          >
            {t('character.currency.spend')}
          </Button>
          <Button
            variant="primary"
            size="md"
            onClick={() => commit(1)}
            disabled={amount <= 0}
            icon={<Plus size={18} />}
            aria-label={t('character.currency.receive')}
          >
            {t('character.currency.receive')}
          </Button>
        </div>
      </Surface>

      {/* Valore esatto di una moneta: campo vuoto col valore attuale suggerito. */}
      <Sheet
        open={exactCoin !== null}
        onClose={() => setExactCoin(null)}
        title={exactCoin ? t('character.currency.set_title', { coin: coinName(exactCoin) }) : undefined}
      >
        {exactCoin && (
          <div className="p-5 space-y-3">
            <Input
              label={t('character.currency.set_label')}
              type="number"
              min={0}
              inputMode="numeric"
              value={exactDraft}
              onChange={setExactDraft}
              placeholder={String(have(exactCoin))}
            />
            <div className="flex gap-2 pt-1">
              <Button variant="secondary" fullWidth onClick={() => setExactCoin(null)}>
                {t('common.cancel')}
              </Button>
              <Button
                variant="primary"
                fullWidth
                disabled={exactDraft === '' || !(Number(exactDraft) >= 0)}
                onClick={() => {
                  setExact(exactCoin, Math.floor(Number(exactDraft)))
                  setExactCoin(null)
                }}
              >
                {t('common.save')}
              </Button>
            </div>
          </div>
        )}
      </Sheet>

      {/* Convert Sheet */}
      <Sheet open={showConvert} onClose={() => setShowConvert(false)} title={t('character.currency.convert')}>
        <div className="p-5 space-y-3">
          <div className="space-y-2">
            <ChipSelect
              label={t('character.currency.convert_from')}
              options={coins.map(({ key, label }) => ({ value: key, label }))}
              value={convertSource}
              onChange={(v) => setConvertSource(v as CoinKey)}
              columns={coins.length as 4 | 5}
            />
            <div className="flex justify-center">
              <Pressable
                onClick={() => {
                  const tmp = convertSource
                  setConvertSource(convertTarget)
                  setConvertTarget(tmp)
                }}
                className="w-11 h-11 rounded-full bg-dnd-surface-raised border border-dnd-gold-dim/40 flex items-center justify-center text-dnd-gold-bright"
                whileTap={{ scale: 0.9, rotate: 180 }}
                aria-label={t('character.currency.swap')}
              >
                <ArrowUpDown size={16} />
              </Pressable>
            </div>
            <ChipSelect
              label={t('character.currency.convert_to')}
              options={coins.map(({ key, label }) => ({ value: key, label }))}
              value={convertTarget}
              onChange={(v) => setConvertTarget(v as CoinKey)}
              columns={coins.length as 4 | 5}
            />
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

          {convertPreview && (
            <p className="text-xs font-body text-dnd-text-faint text-center">{convertPreview}</p>
          )}

          {/* Annulla a sinistra, conferma a destra (convenzione di sistema). */}
          <div className="flex gap-2 pt-1">
            <Button variant="secondary" fullWidth onClick={() => setShowConvert(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="primary"
              fullWidth
              onClick={() => convertMutation.mutate()}
              disabled={!(Math.floor(Number(convertAmount)) >= 1) || convertSource === convertTarget}
              loading={convertMutation.isPending}
              haptic="success"
            >
              {t('character.currency.convert')}
            </Button>
          </div>
        </div>
      </Sheet>
    </Layout>
  )
}

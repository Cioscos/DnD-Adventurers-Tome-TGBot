import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { api } from '@/api/client'
import Sheet from '@/components/ui/Sheet'
import Pressable from '@/components/ui/Pressable'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import ChipSelect from '@/components/ui/ChipSelect'
import { containerTree } from '@/lib/containers'
import { haptic } from '@/auth/telegram'
import type { CoinKey, CoinLocation, Item } from '@/types'

const COIN_LABEL: Record<CoinKey, string> = { platinum: 'PP', gold: 'GP', electrum: 'EP', silver: 'SP', copper: 'CP' }
const PURSE = 'purse'
const toId = (k: string): number | null => (k === PURSE ? null : Number(k))

interface Props {
  charId: number
  items: Item[]
  breakdown: CoinLocation[]
  coin: CoinKey
  /** Posto di partenza preselezionato (null = borsa). */
  from?: number | null
  onClose: () => void
}

/** Sposta monete di una moneta fra borsa e contenitori: da, a, quantità. */
export default function CoinMoveSheet({ charId, items, breakdown, coin: initialCoin, from: initialFrom = null, onClose }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [coin, setCoin] = useState<CoinKey>(initialCoin)
  const [fromKey, setFromKey] = useState(initialFrom == null ? PURSE : String(initialFrom))
  const [toKey, setToKey] = useState<string | null>(null)
  const [qty, setQty] = useState('')

  const heldAt = (k: string) => breakdown.find((b) => b.container_id === toId(k))?.coins[coin] ?? 0
  const places = [
    { key: PURSE, name: t('character.currency.purse') },
    ...containerTree(items).map(({ item }) => ({ key: String(item.id), name: item.name })),
  ]
  const sources = places.filter((p) => heldAt(p.key) > 0)
  const from = sources.some((p) => p.key === fromKey) ? fromKey : (sources[0]?.key ?? fromKey)
  const available = heldAt(from)
  const n = Math.floor(Number(qty)) || 0
  const ok = toKey !== null && toKey !== from && n >= 1 && n <= available

  // Stessa coda delle altre operazioni sulle monete: arrivano in ordine.
  const move = useMutation({
    scope: { id: `currency-${charId}` },
    mutationFn: () => api.currency.move(charId, { coin, amount: n, from_container_id: toId(from), to_container_id: toId(toKey!) }),
    onSuccess: () => { haptic.success(); onClose() },
    onError: () => { haptic.error(); toast.error(t('character.currency.move_error')) },
    onSettled: () => qc.invalidateQueries({ queryKey: ['character', charId] }),
  })

  const row = 'min-h-[44px] flex items-center justify-between gap-2 px-3 rounded-xl border text-left text-sm font-cinzel disabled:opacity-40'
  return (
    <Sheet open onClose={onClose} title={t('character.currency.move')}>
      <div className="p-5 space-y-3">
        <ChipSelect
          label={t('character.currency.move_coin')}
          options={(Object.keys(COIN_LABEL) as CoinKey[]).map((k) => ({ value: k, label: COIN_LABEL[k] }))}
          value={coin}
          onChange={(v) => { setCoin(v as CoinKey); setQty('') }}
          columns={5}
        />
        <div className="space-y-1.5">
          <p className="text-xs font-cinzel uppercase text-dnd-gold-dim">{t('character.currency.convert_from')}</p>
          {sources.length === 0 && <p className="text-xs text-dnd-text-faint">{t('character.currency.none_here')}</p>}
          {sources.map((p) => (
            <Pressable key={p.key} aria-pressed={from === p.key} onClick={() => setFromKey(p.key)}
              className={`${row} w-full ${from === p.key ? 'bg-dnd-gold/20 border-dnd-gold' : 'bg-dnd-surface border-dnd-border'}`}>
              <span className="truncate">{p.name}</span>
              <span className="font-mono tabular-nums text-dnd-text-muted">{heldAt(p.key)}</span>
            </Pressable>
          ))}
        </div>
        <div className="space-y-1.5">
          <p className="text-xs font-cinzel uppercase text-dnd-gold-dim">{t('character.currency.convert_to')}</p>
          {places.filter((p) => p.key !== from).map((p) => (
            <Pressable key={p.key} aria-pressed={toKey === p.key} onClick={() => setToKey(p.key)}
              className={`${row} w-full ${toKey === p.key ? 'bg-dnd-gold/20 border-dnd-gold' : 'bg-dnd-surface border-dnd-border'}`}>
              <span className="truncate">{p.name}</span>
            </Pressable>
          ))}
        </div>
        <Input
          label={t('character.currency.convert_amount')}
          type="number"
          min={1}
          inputMode="numeric"
          value={qty}
          onChange={setQty}
          placeholder="0"
          error={n > available ? t('character.currency.not_enough', { n: available, coin: t(`character.currency.${coin}`) }) : undefined}
        />
        <div className="flex gap-2 pt-1">
          <Button variant="secondary" fullWidth onClick={onClose}>{t('common.cancel')}</Button>
          <Button variant="primary" fullWidth disabled={!ok} loading={move.isPending} onClick={() => move.mutate()}>
            {t('character.currency.move_confirm')}
          </Button>
        </div>
      </div>
    </Sheet>
  )
}

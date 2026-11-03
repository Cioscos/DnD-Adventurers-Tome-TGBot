import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import { PartnerPicker } from '@/pages/inventory/GiveSheet'
import { COIN_ORDER, initialTarget, useTradeMutation } from '@/hooks/useTradeMutation'
import type { CoinKey, SessionParticipant } from '@/types'

interface Props {
  charId: number
  sessionId: number
  partners: SessionParticipant[]
  stash?: boolean
  /** Totale posseduto per moneta (borsa + contenitori). */
  totals: Partial<Record<CoinKey, number>>
  onClose: () => void
}

/** «Dai a…» per monete sciolte: importo per moneta, limitato al totale posseduto. */
export default function GiveCoinsSheet({ charId, sessionId, partners, stash, totals, onClose }: Props) {
  const { t } = useTranslation()
  const [to, setTo] = useState<number | null>(initialTarget(partners, stash))
  const [draft, setDraft] = useState<Partial<Record<CoinKey, string>>>({})
  const give = useTradeMutation(charId, sessionId, onClose)

  const amount = (k: CoinKey) => Math.floor(Number(draft[k])) || 0
  const over = (k: CoinKey) => amount(k) > (totals[k] ?? 0)
  const coins = Object.fromEntries(COIN_ORDER.filter((k) => amount(k) > 0).map((k) => [k, amount(k)])) as Partial<Record<CoinKey, number>>
  const ok = to != null && Object.keys(coins).length > 0 && !COIN_ORDER.some(over)

  return (
    <Sheet open onClose={onClose} title={t('character.inventory.give.title')}>
      <div className="p-5 space-y-3">
        <div className="space-y-2">
          {COIN_ORDER.map((k) => (
            <Input
              key={k}
              label={`${t(`character.currency.${k}`)} (${totals[k] ?? 0})`}
              type="number"
              min={0}
              inputMode="numeric"
              value={draft[k] ?? ''}
              onChange={(v) => setDraft((d) => ({ ...d, [k]: v }))}
              placeholder="0"
              error={over(k) ? t('character.inventory.give.errors.insufficient_funds') : undefined}
            />
          ))}
        </div>
        <PartnerPicker partners={partners} stash={stash} value={to} onChange={setTo} />
        <div className="flex gap-2 pt-1">
          <Button variant="secondary" fullWidth onClick={onClose}>{t('common.cancel')}</Button>
          <Button variant="primary" fullWidth disabled={!ok} loading={give.isPending}
            onClick={() => give.mutate({ from_character_id: charId, to_user_id: to!, coins })}>
            {t('character.inventory.give.confirm')}
          </Button>
        </div>
      </div>
    </Sheet>
  )
}

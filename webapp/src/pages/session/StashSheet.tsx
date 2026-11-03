import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Coins, Minus, Package, Plus } from 'lucide-react'
import Sheet from '@/components/ui/Sheet'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import Pressable from '@/components/ui/Pressable'
import Skeleton from '@/components/ui/Skeleton'
import StashTree from '@/pages/campaign/StashTree'
import GrantItemModal from '@/pages/session/GrantItemModal'
import { api, ApiError } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { useToast } from '@/hooks/useToast'
import { COIN_ORDER } from '@/hooks/useTradeMutation'
import { containerMeta } from '@/lib/containers'
import { formatInt } from '@/lib/format'
import type { CampaignStash, CharacterFull, CoinKey, Currency, Item, SessionParticipant, StashMoveRequest } from '@/types'

type CoinAmounts = Partial<Record<CoinKey, number>>
type Job = { kind: 'take' | 'remove' | 'add'; body: StashMoveRequest }
type Panel = { kind: 'item'; mode: 'take' | 'remove'; item: Item } | { kind: 'coins'; mode: 'take' | 'remove' | 'add' } | { kind: 'grant' }

interface Props {
  sessionId: number
  isGm: boolean
  /** PG con cui il giocatore prende dal deposito; il master non ne ha. */
  myCharId: number | null
  participants: SessionParticipant[]
  gmUserId: number | null
  onClose: () => void
}

/** Importi per moneta; `max` (la cassa) limita prendi/togli, senza `max` si può aggiungere quanto si vuole. */
function CoinsPanel({ title, confirm, max, pending, onSubmit, onClose }: {
  title: string; confirm: string; max?: Currency; pending: boolean; onSubmit: (c: CoinAmounts) => void; onClose: () => void
}) {
  const { t, i18n } = useTranslation()
  const [draft, setDraft] = useState<Partial<Record<CoinKey, string>>>({})
  const amount = (k: CoinKey) => Math.floor(Number(draft[k])) || 0
  const over = (k: CoinKey) => max !== undefined && amount(k) > max[k]
  const coins = Object.fromEntries(COIN_ORDER.filter((k) => amount(k) > 0).map((k) => [k, amount(k)])) as CoinAmounts
  const ok = Object.keys(coins).length > 0 && !COIN_ORDER.some(over)
  return (
    <Sheet open onClose={onClose} title={title} zClassName="z-[60]">
      <div className="p-5 space-y-3">
        {/* prendi/togli: solo le monete che la cassa ha */}
        {COIN_ORDER.filter((k) => max === undefined || max[k] > 0).map((k) => (
          <Input
            key={k}
            label={max ? `${t(`character.currency.${k}`)} (${formatInt(max[k], i18n.language)})` : t(`character.currency.${k}`)}
            type="number"
            min={0}
            inputMode="numeric"
            value={draft[k] ?? ''}
            onChange={(v) => setDraft((d) => ({ ...d, [k]: v }))}
            placeholder="0"
            error={over(k) ? t('character.inventory.give.errors.insufficient_funds') : undefined}
          />
        ))}
        <div className="flex gap-2 pt-1">
          <Button variant="secondary" fullWidth onClick={onClose}>{t('common.cancel')}</Button>
          <Button variant="primary" fullWidth disabled={!ok} loading={pending} onClick={() => onSubmit(coins)}>{confirm}</Button>
        </div>
      </div>
    </Sheet>
  )
}

/** Quantità (pile) o conferma (contenitori, che si muovono interi) per una riga del deposito. */
function ItemPanel({ item, confirm, pending, onSubmit, onClose }: {
  item: Item; confirm: string; pending: boolean; onSubmit: (qty: number | undefined) => void; onClose: () => void
}) {
  const { t } = useTranslation()
  const stepper = item.quantity > 1 && !containerMeta(item)
  const [qty, setQty] = useState(item.quantity)
  const stepBtn = 'min-h-[44px] min-w-[44px] flex items-center justify-center rounded-xl border border-dnd-border'
  return (
    <Sheet open onClose={onClose} title={item.name} zClassName="z-[60]">
      <div className="p-5 space-y-3">
        {stepper && (
          <div className="flex items-center justify-center gap-3">
            <Pressable aria-label={t('character.inventory.containers.qty_minus')} onClick={() => setQty((v) => Math.max(1, v - 1))} className={stepBtn}>
              <Minus size={16} />
            </Pressable>
            <span className="font-mono tabular-nums min-w-[5rem] whitespace-nowrap text-center">{qty} / {item.quantity}</span>
            <Pressable aria-label={t('character.inventory.containers.qty_plus')} onClick={() => setQty((v) => Math.min(item.quantity, v + 1))} className={stepBtn}>
              <Plus size={16} />
            </Pressable>
          </div>
        )}
        <div className="flex gap-2 pt-1">
          <Button variant="secondary" fullWidth onClick={onClose}>{t('common.cancel')}</Button>
          <Button variant="primary" fullWidth loading={pending} onClick={() => onSubmit(stepper && qty < item.quantity ? qty : undefined)}>{confirm}</Button>
        </div>
      </div>
    </Sheet>
  )
}

/** Deposito di gruppo dentro la sessione: i giocatori «Prendi», il master «Metti nel deposito» / «Togli». */
export default function StashSheet({ sessionId, isGm, myCharId, participants, gmUserId, onClose }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [panel, setPanel] = useState<Panel | null>(null)
  const { data, isLoading } = useQuery({ queryKey: ['session-stash', sessionId], queryFn: () => api.sessions.stash(sessionId), refetchInterval: 10_000 })

  const act = useMutation({
    mutationFn: ({ kind, body }: Job): Promise<CharacterFull | CampaignStash> => {
      if (kind === 'take') return api.sessions.stashTake(sessionId, { to_character_id: myCharId!, ...body })
      if (kind === 'remove') return api.sessions.stashGmRemove(sessionId, body)
      return api.sessions.stashGmAdd(sessionId, { coins: body.coins })
    },
    onSuccess: (res, { kind }) => {
      // «Prendi» restituisce il PG aggiornato, come «Dai a…».
      if (kind === 'take' && myCharId != null) qc.setQueryData(['character', myCharId], res)
      qc.invalidateQueries({ queryKey: ['session-stash', sessionId] })
      qc.invalidateQueries({ queryKey: ['session-feed'] })
      haptic.success()
      setPanel(null)
    },
    onError: (e) => {
      const detail = e instanceof ApiError && typeof e.detail === 'string' ? e.detail : ''
      const key = e instanceof ApiError && e.status === 410 ? 'closed' : detail
      toast.error(t(`character.inventory.give.errors.${key}`, { defaultValue: t('common.action_failed') }))
      qc.invalidateQueries({ queryKey: ['session-stash', sessionId] })
    },
  })

  const canTake = !isGm && myCharId != null
  const hasCoins = !!data && COIN_ORDER.some((k) => data.currency[k] > 0)
  const verb = t(isGm ? 'campaign.stash_remove' : 'campaign.stash_take')
  const mode = isGm ? 'remove' : 'take'
  const rowBtn = (onClick: () => void) => (
    <Button variant="secondary" size="sm" onClick={onClick} icon={<Package size={14} />}>{verb}</Button>
  )

  return (
    <>
      <Sheet open onClose={onClose} title={t('campaign.stash')}>
        <div className="p-5 space-y-3">
          {isLoading || !data ? (
            <Skeleton.Rect height="120px" />
          ) : (
            <StashTree
              items={data.items}
              currency={data.currency}
              coinsAction={(isGm || canTake) && hasCoins ? rowBtn(() => setPanel({ kind: 'coins', mode })) : undefined}
              renderAction={isGm || canTake ? (item) => rowBtn(() => setPanel({ kind: 'item', mode, item })) : undefined}
            />
          )}
          {isGm && (
            <div className="space-y-2 pt-1">
              <Button variant="primary" fullWidth icon={<Package size={16} />} onClick={() => setPanel({ kind: 'grant' })}>{t('campaign.stash_put')}</Button>
              <Button variant="secondary" fullWidth icon={<Coins size={16} />} onClick={() => setPanel({ kind: 'coins', mode: 'add' })}>{t('campaign.stash_put_coins')}</Button>
            </div>
          )}
        </div>
      </Sheet>

      {panel?.kind === 'item' && (
        <ItemPanel
          item={panel.item}
          confirm={verb}
          pending={act.isPending}
          onClose={() => setPanel(null)}
          onSubmit={(quantity) => act.mutate({ kind: panel.mode, body: { item_id: panel.item.id, ...(quantity ? { quantity } : {}) } })}
        />
      )}
      {panel?.kind === 'coins' && (
        <CoinsPanel
          title={t('campaign.stash_coins')}
          confirm={panel.mode === 'add' ? t('campaign.stash_put') : verb}
          max={panel.mode === 'add' ? undefined : data?.currency}
          pending={act.isPending}
          onClose={() => setPanel(null)}
          onSubmit={(coins) => act.mutate({ kind: panel.mode, body: { coins } })}
        />
      )}
      {panel?.kind === 'grant' && (
        <GrantItemModal stash sessionId={sessionId} participants={participants} gmUserId={gmUserId} onClose={() => setPanel(null)} />
      )}
    </>
  )
}

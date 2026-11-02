import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Minus, Plus, User } from 'lucide-react'
import Sheet from '@/components/ui/Sheet'
import Pressable from '@/components/ui/Pressable'
import Button from '@/components/ui/Button'
import { COIN_ORDER, COIN_ABBR, useTradeMutation } from '@/hooks/useTradeMutation'
import { containerMeta } from '@/lib/containers'
import type { CoinKey, Item, SessionParticipant } from '@/types'

const partnerName = (p: SessionParticipant) => p.display_name || `#${p.user_id}`

export function PartnerPicker({ partners, value, onChange }: { partners: SessionParticipant[]; value: number | null; onChange: (id: number) => void }) {
  const { t } = useTranslation()
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-cinzel uppercase text-dnd-gold-dim">{t('character.inventory.give.to')}</p>
      {partners.map((p) => (
        <Pressable key={p.user_id} aria-pressed={value === p.user_id} onClick={() => onChange(p.user_id)}
          className={`w-full min-h-[44px] flex items-center gap-2 px-3 rounded-xl border text-left text-sm font-cinzel ${value === p.user_id ? 'bg-dnd-gold/20 border-dnd-gold' : 'bg-dnd-surface border-dnd-border'}`}>
          <User size={16} className="text-dnd-gold shrink-0" />
          <span className="truncate">{partnerName(p)}</span>
        </Pressable>
      ))}
    </div>
  )
}

interface Props {
  charId: number
  sessionId: number
  partners: SessionParticipant[]
  item: Item
  items: Item[]
  onClose: () => void
}

/** «Dai a…» per un oggetto, una pila o un contenitore (con tutto il contenuto). */
export default function GiveSheet({ charId, sessionId, partners, item, items, onClose }: Props) {
  const { t } = useTranslation()
  const p = 'character.inventory.give.'
  const [to, setTo] = useState<number | null>(partners.length === 1 ? partners[0].user_id : null)
  const stepper = item.quantity > 1
  const [qty, setQty] = useState(item.quantity)
  const give = useTradeMutation(charId, sessionId, onClose)

  // Riepilogo del contenitore: discendenti a ogni livello + monete proprie e dei sotto-contenitori.
  const meta = containerMeta(item)
  const descendants: Item[] = []
  const walk = (id: number) => items.filter((i) => i.container_id === id).forEach((c) => { descendants.push(c); walk(c.id) })
  if (meta) walk(item.id)
  const coins: Partial<Record<CoinKey, number>> = {}
  for (const c of [item, ...descendants]) {
    const cc = containerMeta(c)?.coins ?? {}
    for (const k of COIN_ORDER) if ((cc[k] ?? 0) > 0) coins[k] = (coins[k] ?? 0) + (cc[k] ?? 0)
  }
  const coinText = COIN_ORDER.filter((k) => coins[k]).map((k) => `${coins[k]} ${COIN_ABBR[k]}`).join(' · ')

  const confirm = () => {
    if (to == null) return
    give.mutate({
      from_character_id: charId,
      to_user_id: to,
      item_id: item.id,
      ...(stepper && qty < item.quantity ? { quantity: qty } : {}),
    })
  }
  const stepBtn = 'min-h-[44px] min-w-[44px] flex items-center justify-center rounded-xl border border-dnd-border'
  return (
    <Sheet open onClose={onClose} title={t(p + 'title')}>
      <div className="p-5 space-y-3">
        <p className="font-cinzel text-sm truncate">{item.name}</p>
        {meta && (
          <p data-testid="give-summary" className="text-xs text-dnd-text-muted">
            {t(p + 'summary', { count: descendants.length })}
            {coinText && <span className="font-mono tabular-nums"> · {coinText}</span>}
          </p>
        )}
        {stepper && (
          <div className="flex items-center justify-center gap-3">
            <Pressable aria-label={t('character.inventory.containers.qty_minus')} onClick={() => setQty((v) => Math.max(1, v - 1))} className={stepBtn}>
              <Minus size={16} />
            </Pressable>
            <span className="font-mono tabular-nums w-16 text-center">{qty} / {item.quantity}</span>
            <Pressable aria-label={t('character.inventory.containers.qty_plus')} onClick={() => setQty((v) => Math.min(item.quantity, v + 1))} className={stepBtn}>
              <Plus size={16} />
            </Pressable>
          </div>
        )}
        <PartnerPicker partners={partners} value={to} onChange={setTo} />
        <div className="flex gap-2 pt-1">
          <Button variant="secondary" fullWidth onClick={onClose}>{t('common.cancel')}</Button>
          <Button variant="primary" fullWidth disabled={to == null} loading={give.isPending} onClick={confirm}>
            {t(p + 'confirm')}
          </Button>
        </div>
      </div>
    </Sheet>
  )
}

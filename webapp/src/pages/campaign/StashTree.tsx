import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Package } from 'lucide-react'
import Pressable from '@/components/ui/Pressable'
import ExpandChevron from '@/components/ui/ExpandChevron'
import { COIN_ORDER, COIN_ABBR } from '@/hooks/useTradeMutation'
import { containerMeta } from '@/lib/containers'
import { formatInt } from '@/lib/format'
import type { Currency, Item } from '@/types'

interface Props {
  items: Item[]
  currency: Currency
  /** Azione opzionale per riga (es. «Prendi»); il contenitore la riceve come ogni oggetto. */
  renderAction?: (item: Item) => ReactNode
}

function descendantCount(items: Item[], id: number): number {
  return items
    .filter((i) => i.container_id === id)
    .reduce((n, c) => n + 1 + descendantCount(items, c.id), 0)
}

function Node({ item, items, depth, renderAction }: { item: Item; items: Item[]; depth: number; renderAction?: Props['renderAction'] }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const children = items.filter((i) => i.container_id === item.id).sort((a, b) => a.id - b.id)
  const box = containerMeta(item) !== null
  const label = (
    <span className="min-w-0 flex-1 text-left break-words">
      <span className="font-cinzel text-sm text-dnd-text">{item.name}</span>
      {item.quantity > 1 && <span className="font-mono tabular-nums text-dnd-text-muted"> ×{item.quantity}</span>}
      {box && <span className="text-xs text-dnd-text-muted"> · {t('campaign.stash_items', { count: descendantCount(items, item.id) })}</span>}
    </span>
  )
  return (
    <li>
      <div className="flex items-center gap-2 min-h-[44px]" style={{ paddingLeft: depth * 14 }}>
        {box ? (
          <Pressable onClick={() => setOpen((o) => !o)} aria-expanded={open} className="flex-1 min-w-0 min-h-[44px] flex items-center gap-2 text-left">
            <Package size={16} className="shrink-0 text-dnd-gold" />
            {label}
            <ExpandChevron open={open} className="text-dnd-gold-dim" />
          </Pressable>
        ) : (
          label
        )}
        {renderAction && <div className="shrink-0">{renderAction(item)}</div>}
      </div>
      {box && open && children.length > 0 && (
        <ul className="space-y-1 mt-1">{children.map((c) => <Node key={c.id} item={c} items={items} depth={depth + 1} renderAction={renderAction} />)}</ul>
      )}
    </li>
  )
}

/** Albero di contenitori + cassa del deposito di gruppo. Sola lettura salvo `renderAction`. */
export default function StashTree({ items, currency, renderAction }: Props) {
  const { t, i18n } = useTranslation()
  const roots = items.filter((i) => i.container_id == null).sort((a, b) => a.id - b.id)
  const coins = COIN_ORDER.filter((k) => currency[k] > 0)
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between gap-3 min-h-[44px]">
        <span className="font-cinzel text-sm text-dnd-text shrink-0">{t('campaign.stash_coins')}</span>
        <span className="min-w-0 text-right font-mono tabular-nums text-sm text-dnd-gold-bright break-words">
          {coins.length > 0
            ? coins.map((k) => `${formatInt(currency[k], i18n.language)} ${COIN_ABBR[k]}`).join(' · ')
            : '0'}
        </span>
      </div>
      {roots.length === 0 ? (
        <p className="text-sm text-dnd-text-muted italic">{t('campaign.stash_empty')}</p>
      ) : (
        <ul className="space-y-1">{roots.map((i) => <Node key={i.id} item={i} items={items} depth={0} renderAction={renderAction} />)}</ul>
      )}
    </div>
  )
}

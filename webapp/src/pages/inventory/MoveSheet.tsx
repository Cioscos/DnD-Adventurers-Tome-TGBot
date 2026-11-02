import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Folder, Package, Plus, Minus } from 'lucide-react'
import Sheet from '@/components/ui/Sheet'
import Pressable from '@/components/ui/Pressable'
import Button from '@/components/ui/Button'
import { containerMeta, containerTree, movedWeight } from '@/lib/containers'
import { useUnitSettings, formatWeight, formatWeightValue } from '@/store/unitSettings'
import type { Item } from '@/types'

interface Props {
  items: Item[]
  moving: Item[]
  /** Contenitore in cui si trovano ora gli oggetti (null = fuori). */
  currentId: number | null
  onMove: (containerId: number | null, quantity?: number) => void
  onNewContainer: () => void
  onClose: () => void
  pending?: boolean
}

export default function MoveSheet({ items, moving, currentId, onMove, onNewContainer, onClose, pending }: Props) {
  const { t } = useTranslation()
  const system = useUnitSettings((s) => s.system)
  const single = moving.length === 1 ? moving[0] : null
  const stepper = single != null && single.quantity > 1
  const [qty, setQty] = useState(single?.quantity ?? 1)
  const p = 'character.inventory.containers.'

  // Un contenitore spostato non può finire in sé stesso né nei discendenti.
  const byId = new Map(items.map((i) => [i.id, i]))
  const movingIds = new Set(moving.map((i) => i.id))
  const insideMoved = (id: number): boolean => {
    for (let c = byId.get(id); c; c = c.container_id == null ? undefined : byId.get(c.container_id)) {
      if (movingIds.has(c.id)) return true
    }
    return false
  }
  const weight = moving.reduce((s, i) => s + movedWeight(i, i === single && stepper ? qty : undefined), 0)
  const q = stepper && single != null && qty < single.quantity ? qty : undefined

  const row = 'w-full min-h-[44px] flex items-center gap-2 p-3 rounded-xl border text-left disabled:opacity-40 bg-dnd-surface border-dnd-border'
  const stepBtn = 'min-h-[44px] min-w-[44px] flex items-center justify-center rounded-xl border border-dnd-border'
  return (
    <Sheet open onClose={onClose} title={t(p + 'move_title')}>
      <div className="p-5 space-y-2">
        {stepper && (
          <div className="flex items-center justify-center gap-3 pb-2">
            <Pressable aria-label={t(p + 'qty_minus')} onClick={() => setQty((v) => Math.max(1, v - 1))} className={stepBtn}>
              <Minus size={16} />
            </Pressable>
            <span className="font-mono tabular-nums w-16 text-center">{qty} / {single.quantity}</span>
            <Pressable aria-label={t(p + 'qty_plus')} onClick={() => setQty((v) => Math.min(single.quantity, v + 1))} className={stepBtn}>
              <Plus size={16} />
            </Pressable>
          </div>
        )}
        <Pressable disabled={currentId === null || pending} onClick={() => onMove(null, q)} className={row}>
          <Package size={18} className="text-dnd-gold shrink-0" />
          <span className="flex-1 font-cinzel text-sm">{t(p + 'outside')}</span>
        </Pressable>
        {containerTree(items).map(({ item, depth }) => {
          const meta = containerMeta(item)!
          const used = item.container_stats?.contents_weight ?? 0
          const over = meta.capacity_lb != null && used + weight > meta.capacity_lb
          return (
            <Pressable
              key={item.id}
              disabled={item.id === currentId || insideMoved(item.id) || pending}
              onClick={() => onMove(item.id, q)}
              className={row}
            >
              <span style={{ width: depth * 16 }} className="shrink-0" aria-hidden />
              <Folder size={18} className="text-dnd-gold shrink-0" />
              <span className="flex-1 min-w-0">
                <span className="block font-cinzel text-sm truncate">{item.name}</span>
                <span className="block text-xs text-dnd-text-muted font-mono tabular-nums">
                  {meta.capacity_lb != null
                    ? `${formatWeightValue(used, system)} / ${formatWeight(meta.capacity_lb, system)}`
                    : formatWeight(used, system)}
                </span>
              </span>
              {over && <span className="text-dnd-crimson-bright text-xs shrink-0">⚠ {t(p + 'over_short')}</span>}
            </Pressable>
          )
        })}
        <Button variant="secondary" fullWidth icon={<Plus size={16} />} onClick={onNewContainer}>
          {t(p + 'new_here')}
        </Button>
      </div>
    </Sheet>
  )
}

import { useTranslation } from 'react-i18next'
import { Folder, AlertTriangle, ChevronRight } from 'lucide-react'
import Pressable from '@/components/ui/Pressable'
import { containerMeta } from '@/lib/containers'
import { useUnitSettings, formatWeightValue, formatWeight } from '@/store/unitSettings'
import type { Item } from '@/types'

/** Cartella del bozzetto B: nome, conteggi, peso/capienza. */
export default function ContainerCard({ item, onOpen }: { item: Item; onOpen: () => void }) {
  const { t } = useTranslation()
  const system = useUnitSettings((s) => s.system)
  const meta = containerMeta(item)
  const stats = item.container_stats
  const over = stats?.over_capacity ?? false
  const weight = stats ? formatWeightValue(stats.contents_weight, system) : '0'
  return (
    <Pressable
      onClick={onOpen}
      className={`w-full min-h-[44px] flex items-center gap-3 p-3 rounded-xl bg-dnd-surface border text-left ${over ? 'border-dnd-crimson-bright' : 'border-dnd-border'}`}
    >
      <Folder size={20} className="text-dnd-gold shrink-0" />
      <span className="flex-1 min-w-0">
        <span className="block font-cinzel text-sm text-dnd-gold-bright truncate">{item.name}</span>
        <span className="block text-xs text-dnd-text-muted font-mono tabular-nums">
          {t('character.inventory.containers.items', { count: stats?.items_count ?? 0 })}
          {(stats?.containers_count ?? 0) > 0 && ` · ${t('character.inventory.containers.boxes', { count: stats!.containers_count })}`}
          {' · '}
          {meta?.capacity_lb != null ? `${weight} / ${formatWeight(meta.capacity_lb, system)}` : formatWeight(stats?.contents_weight ?? 0, system)}
        </span>
      </span>
      {meta && !meta.counts_weight && (
        <span className="text-xs px-2 py-0.5 rounded-full border border-dnd-border text-dnd-text-muted">
          {t('character.inventory.containers.no_weight')}
        </span>
      )}
      {over && (
        <AlertTriangle size={16} className="text-dnd-crimson-bright shrink-0" aria-label={t('character.inventory.containers.over')} />
      )}
      <ChevronRight size={16} className="text-dnd-text-muted shrink-0" />
    </Pressable>
  )
}

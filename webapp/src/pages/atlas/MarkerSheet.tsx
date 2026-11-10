import { notifyMutationError } from '@/lib/mutationError'
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Eye, EyeOff, Map as MapIcon, Move, Pencil, Trash2 } from 'lucide-react'
import Sheet from '@/components/ui/Sheet'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import Button from '@/components/ui/Button'
import { api } from '@/api/client'
import { resolveType, visibilityKey } from '@/lib/atlasIcons'
import type { AtlasMarker } from '@/types'

interface Props {
  open: boolean
  campaignId: number
  marker: AtlasMarker
  isGm: boolean
  /** Nome della mappa collegata, se il marker porta a una sottomappa visibile. */
  linkName: string | null
  onClose: () => void
  onOpenLink: (mapId: number) => void
  onEdit: () => void
  onMove: () => void
}

/** Scheda del marker (bozza 2): tipo, nome, autore, visibilità, descrizione e azioni. */
export default function MarkerSheet({ open, campaignId, marker, isGm, linkName, onClose, onOpenLink, onEdit, onMove }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const { Icon, color, label } = resolveType(marker.type)
  const refresh = () => qc.invalidateQueries({ queryKey: ['atlas-markers', campaignId, marker.map_id] })
  const fail = (e: unknown) => notifyMutationError(e)

  const next = marker.visibility === 'public' ? 'private' : 'public'
  const toggle = useMutation({
    mutationFn: () => api.atlas.setVisibility(campaignId, marker.id, next),
    onSuccess: refresh,
    onError: fail,
  })
  const remove = useMutation({
    mutationFn: () => api.atlas.deleteMarker(campaignId, marker.id),
    onSuccess: () => { setConfirmDelete(false); refresh(); onClose() },
    onError: fail,
  })
  const toggleKey = isGm ? (next === 'public' ? 'atlas.reveal' : 'atlas.hide') : (next === 'public' ? 'atlas.make_public' : 'atlas.make_private')

  return (
    <>
      <Sheet open={open && !confirmDelete} onClose={onClose}>
        <div className="p-5 space-y-4">
          <div className="flex items-start gap-3">
            <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-current bg-dnd-surface ${color}`}>
              <Icon size={22} aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-xs uppercase tracking-wider font-cinzel font-bold text-dnd-gold-dim">{label(t)}</p>
              <h2 className="break-words font-display text-xl font-bold text-dnd-gold-bright">{marker.name}</h2>
              <p className="text-xs font-body text-dnd-text-muted">
                {marker.author_role === 'gm' ? t('atlas.by_gm') : t('atlas.by_player', { name: marker.author_name ?? '' })}
              </p>
            </div>
            <span className="shrink-0 rounded-lg border border-dnd-chip-border bg-dnd-chip-bg px-2.5 py-1 text-xs uppercase tracking-wider font-cinzel font-bold text-dnd-gold-bright">
              {t(visibilityKey(isGm, marker.visibility))}
            </span>
          </div>
          {marker.description && (
            <p className="whitespace-pre-wrap break-words text-sm font-body text-dnd-text">{marker.description}</p>
          )}
          {marker.link_map_id != null && (
            <Button fullWidth size="lg" icon={<MapIcon size={18} />} onClick={() => onOpenLink(marker.link_map_id!)}>
              {t('atlas.open_map', { name: linkName ?? '' })}
            </Button>
          )}
          {(marker.can_edit || marker.can_delete) && (
            <div className="grid grid-cols-2 gap-2">
              {marker.can_edit && (
                <>
                  <Button variant="secondary" icon={<Pencil size={16} />} onClick={onEdit}>{t('common.edit')}</Button>
                  <Button variant="secondary" icon={<Move size={16} />} onClick={onMove}>{t('atlas.move')}</Button>
                  <Button
                    variant="secondary"
                    icon={next === 'public' ? <Eye size={16} /> : <EyeOff size={16} />}
                    loading={toggle.isPending}
                    onClick={() => toggle.mutate()}
                  >
                    {t(toggleKey)}
                  </Button>
                </>
              )}
              {marker.can_delete && (
                <Button variant="danger" icon={<Trash2 size={16} />} onClick={() => setConfirmDelete(true)}>{t('common.delete')}</Button>
              )}
            </div>
          )}
        </div>
      </Sheet>
      <ConfirmSheet
        open={open && confirmDelete}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => remove.mutate()}
        title={t('atlas.marker_delete_title')}
        body={marker.name}
        confirmLabel={t('common.delete')}
        loading={remove.isPending}
      />
    </>
  )
}

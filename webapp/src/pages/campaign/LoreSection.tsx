import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Plus } from 'lucide-react'
import Button from '@/components/ui/Button'
import Pressable from '@/components/ui/Pressable'
import FilterChip from '@/components/ui/FilterChip'
import SectionDivider from '@/components/ui/SectionDivider'
import Skeleton from '@/components/ui/Skeleton'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import LoreEditorSheet from '@/pages/campaign/LoreEditorSheet'
import LoreViewModal from '@/pages/campaign/LoreViewModal'
import { api } from '@/api/client'
import { haptic } from '@/auth/telegram'
import { notifyMutationError } from '@/lib/mutationError'
import type { LoreRead } from '@/types'

/** Sezione Lore della campagna: il master vede bozze e rivelate, i giocatori solo le rivelate. */
export default function LoreSection({ campaignId, isGm }: { campaignId: number; isGm: boolean }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const key = ['lore', campaignId]
  const [tag, setTag] = useState<string | null>(null)
  const [viewId, setViewId] = useState<number | null>(null)
  const [editing, setEditing] = useState<LoreRead | 'new' | null>(null)
  const [deleting, setDeleting] = useState<LoreRead | null>(null)

  const { data: entries, isLoading } = useQuery({ queryKey: key, queryFn: () => api.lore.list(campaignId) })
  const tags = useMemo(() => [...new Set((entries ?? []).flatMap((e) => e.tags))].sort(), [entries])
  const shown = (entries ?? []).filter((e) => tag === null || e.tags.includes(tag))

  const toggle = useMutation({
    mutationFn: (e: LoreRead) => (e.revealed ? api.lore.hide(campaignId, e.id) : api.lore.reveal(campaignId, e.id)),
    onSuccess: () => { haptic.success(); qc.invalidateQueries({ queryKey: key }) },
    onError: () => notifyMutationError(),
  })
  const del = useMutation({
    mutationFn: (e: LoreRead) => api.lore.remove(campaignId, e.id),
    onSuccess: () => { setDeleting(null); qc.invalidateQueries({ queryKey: key }) },
    onError: () => { setDeleting(null); notifyMutationError() },
  })

  return (
    <>
      <SectionDivider>{t('campaign.lore.title')}</SectionDivider>
      {isGm && (
        <div className="mb-2">
          <Button variant="secondary" size="sm" icon={<Plus size={14} />} onClick={() => setEditing('new')}>
            {t('campaign.lore.add')}
          </Button>
        </div>
      )}
      {tags.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-2">
          <FilterChip label={t('campaign.lore.all')} selected={tag === null} onToggle={() => setTag(null)} />
          {tags.map((x) => (
            <FilterChip key={x} label={x} selected={tag === x} onToggle={() => setTag(tag === x ? null : x)} />
          ))}
        </div>
      )}
      {isLoading ? (
        <Skeleton.Rect height="72px" />
      ) : shown.length === 0 ? (
        <p className="text-sm text-dnd-text-muted italic">{t(isGm ? 'campaign.lore.empty_gm' : 'campaign.lore.empty_player')}</p>
      ) : (
        <div className="space-y-2" data-testid="lore-list">
          {shown.map((e) => (
            <div key={e.id} className="border-b border-dnd-border/60 px-1 py-2">
              <Pressable onClick={() => setViewId(e.id)} className="block w-full min-h-[44px] text-left">
                <p className="font-body font-semibold text-sm text-dnd-text break-words">
                  {e.title}
                  {!e.revealed && (
                    <span className="ml-2 align-middle inline-block rounded-full border border-dnd-border-strong px-2 py-0.5 text-xs font-cinzel uppercase tracking-wider text-dnd-text-muted">
                      {t('campaign.lore.draft')}
                    </span>
                  )}
                </p>
                {e.tags.length > 0 && (
                  <p className="text-xs text-dnd-text-muted font-body break-words">{e.tags.join(' · ')}</p>
                )}
              </Pressable>
              {isGm && (
                <div className="mt-2 flex flex-wrap gap-2">
                  <Button variant={e.revealed ? 'secondary' : 'primary'} size="sm" loading={toggle.isPending && toggle.variables?.id === e.id} onClick={() => toggle.mutate(e)}>
                    {t(e.revealed ? 'campaign.lore.hide' : 'campaign.lore.reveal')}
                  </Button>
                  <Button variant="secondary" size="sm" onClick={() => setEditing(e)}>{t('common.edit')}</Button>
                  <Button variant="danger" size="sm" onClick={() => setDeleting(e)}>{t('common.delete')}</Button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <LoreViewModal
        open={viewId !== null}
        campaignId={campaignId}
        lore={entries?.find((e) => e.id === viewId) ?? null}
        onClose={() => setViewId(null)}
      />
      <LoreEditorSheet
        open={editing !== null}
        campaignId={campaignId}
        lore={editing === 'new' ? null : editing}
        onClose={() => setEditing(null)}
      />
      <ConfirmSheet
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        onConfirm={() => deleting && del.mutate(deleting)}
        loading={del.isPending}
        title={t('campaign.lore.delete_title')}
        body={t('campaign.lore.delete_body')}
        confirmLabel={t('campaign.lore.delete_confirm')}
      />
    </>
  )
}

import { notifyMutationError, actionFailedKey } from '@/lib/mutationError'
import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import Sheet from '@/components/ui/Sheet'
import ConfirmSheet from '@/components/ui/ConfirmSheet'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import { api, ApiError } from '@/api/client'
import { downscaleImage } from '@/lib/downscaleImage'
import { useToast } from '@/hooks/useToast'
import type { AtlasMap } from '@/types'

interface Props { open: boolean; campaignId: number; map: AtlasMap; onClose: () => void }

/** Il master gestisce la mappa: rinomina, sostituisci immagine, nascondi/rivela, elimina. */
export default function MapManageSheet({ open, campaignId, map, onClose }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const navigate = useNavigate()
  const fileRef = useRef<HTMLInputElement>(null)
  const [name, setName] = useState(map.name)
  const [confirmDelete, setConfirmDelete] = useState(false)

  useEffect(() => { if (open) { setName(map.name); setConfirmDelete(false) } }, [open, map.name])

  const refresh = () => qc.invalidateQueries({ queryKey: ['atlas-maps', campaignId] })
  const fail = (e: unknown) => notifyMutationError(e)

  const rename = useMutation({
    mutationFn: () => api.atlas.renameMap(campaignId, map.id, name.trim()),
    onSuccess: () => { refresh(); onClose() },
    onError: fail,
  })
  const toggle = useMutation({
    mutationFn: () => (map.revealed ? api.atlas.hideMap(campaignId, map.id) : api.atlas.revealMap(campaignId, map.id)),
    onSuccess: () => { refresh(); onClose() },
    onError: fail,
  })
  const replace = useMutation({
    mutationFn: async (file: File) => {
      let small: File
      try {
        small = await downscaleImage(file)
      } catch {
        throw new Error('decode')
      }
      const fd = new FormData()
      fd.append('file', small)
      return api.atlas.replaceImage(campaignId, map.id, fd)
    },
    onSuccess: () => { refresh(); onClose() },
    onError: (e) => toast.error(t(
      e instanceof ApiError
        ? (e.status === 400 ? 'atlas.err_upload' : actionFailedKey(e))
        : e.message === 'decode' ? 'atlas.err_image' : actionFailedKey(e),
    )),
  })
  const remove = useMutation({
    mutationFn: () => api.atlas.deleteMap(campaignId, map.id),
    onSuccess: () => {
      qc.removeQueries({ queryKey: ['atlas-markers', campaignId, map.id] })
      refresh()
      navigate(`/campaign/${campaignId}`, { replace: true })
    },
    onError: fail,
  })

  return (
    <>
      <Sheet open={open && !confirmDelete} onClose={onClose} title={t('atlas.manage_title')}>
        <div className="p-5 space-y-3">
          <Input label={t('atlas.name_label')} value={name} onChange={(v: string) => setName(v.slice(0, 80))} />
          <Button fullWidth disabled={!name.trim() || name.trim() === map.name} loading={rename.isPending} onClick={() => rename.mutate()}>
            {t('atlas.rename')}
          </Button>
          <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; if (f) replace.mutate(f) }} />
          <Button variant="secondary" fullWidth loading={replace.isPending} onClick={() => fileRef.current?.click()}>
            {t('atlas.replace_image')}
          </Button>
          <Button variant="secondary" fullWidth loading={toggle.isPending} onClick={() => toggle.mutate()}>
            {t(map.revealed ? 'atlas.hide_map' : 'atlas.reveal_map')}
          </Button>
          <Button variant="danger" fullWidth onClick={() => setConfirmDelete(true)}>{t('common.delete')}</Button>
        </div>
      </Sheet>
      <ConfirmSheet
        open={open && confirmDelete}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => remove.mutate()}
        title={t('atlas.delete_title')}
        body={map.marker_count > 0 ? t('atlas.delete_body', { count: map.marker_count }) : undefined}
        confirmLabel={t('common.delete')}
        loading={remove.isPending}
      />
    </>
  )
}

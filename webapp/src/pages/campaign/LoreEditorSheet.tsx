import { actionFailedKey } from '@/lib/mutationError'
import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import ChipInput from '@/components/ui/ChipInput'
import Button from '@/components/ui/Button'
import { api, ApiError } from '@/api/client'
import { useToast } from '@/hooks/useToast'
import type { LoreRead } from '@/types'

interface Props {
  open: boolean
  campaignId: number
  /** null = nuova voce. */
  lore: LoreRead | null
  onClose: () => void
}

/** Un allegato (immagine o audio): file nuovo, oppure quello già salvato con «Rimuovi». */
function FilePick({ label, pick, accept, file, existing, removed, onFile, onRemove }: {
  label: string; pick: string; accept: string; file: File | null; existing: boolean; removed: boolean
  onFile: (f: File | null) => void; onRemove: () => void
}) {
  const { t } = useTranslation()
  const ref = useRef<HTMLInputElement>(null)
  const has = file !== null || (existing && !removed)
  return (
    <div>
      <span className="block text-xs uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">{label}</span>
      <div className="flex flex-wrap items-center gap-2">
        <input ref={ref} type="file" accept={accept} className="hidden" onChange={(e) => { onFile(e.target.files?.[0] ?? null); e.target.value = '' }} />
        <Button variant="secondary" size="sm" onClick={() => ref.current?.click()}>{pick}</Button>
        {has && <span className="min-w-0 break-all text-xs text-dnd-text-muted font-body">{file?.name ?? '✓'}</span>}
        {has && (
          <Button variant="secondary" size="sm" onClick={() => (file ? onFile(null) : onRemove())}>{t('campaign.lore.remove_file')}</Button>
        )}
      </div>
    </div>
  )
}

export default function LoreEditorSheet({ open, campaignId, lore, onClose }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [image, setImage] = useState<File | null>(null)
  const [audio, setAudio] = useState<File | null>(null)
  const [rmImage, setRmImage] = useState(false)
  const [rmAudio, setRmAudio] = useState(false)

  useEffect(() => {
    if (!open) return
    setTitle(lore?.title ?? '')
    setBody(lore?.body ?? '')
    setTags(lore?.tags ?? [])
    setImage(null); setAudio(null); setRmImage(false); setRmAudio(false)
  }, [open, lore])

  const save = useMutation({
    mutationFn: () => {
      const fd = new FormData()
      fd.append('title', title.trim())
      fd.append('body', body.trim())
      fd.append('tags', JSON.stringify(tags))
      if (image) fd.append('image', image)
      if (audio) fd.append('audio', audio)
      if (lore) {
        if (rmImage && !image) fd.append('remove_image', 'true')
        if (rmAudio && !audio) fd.append('remove_audio', 'true')
        return api.lore.update(campaignId, lore.id, fd)
      }
      return api.lore.create(campaignId, fd)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['lore', campaignId] })
      onClose()
    },
    onError: (e) => toast.error(t(e instanceof ApiError && e.status === 400 ? 'campaign.lore.err_file' : actionFailedKey(e))),
  })

  return (
    <Sheet open={open} onClose={onClose} title={t(lore ? 'campaign.lore.edit_title' : 'campaign.lore.new_title')}>
      <div className="p-5 space-y-3">
        <Input label={t('campaign.lore.title_label')} value={title} onChange={setTitle} />
        <Input variant="textarea" rows={8} label={t('campaign.lore.body_label')} value={body} onChange={setBody} />
        <ChipInput
          values={tags}
          onChange={setTags}
          label={<span className="block text-xs uppercase tracking-wider mb-1.5 font-cinzel font-bold text-dnd-gold-dim">{t('campaign.lore.tags_label')}</span>}
        />
        <FilePick
          label={t('campaign.lore.image')} pick={t('campaign.lore.pick_image')} accept="image/png,image/jpeg,image/webp,image/gif"
          file={image} existing={!!lore?.has_image} removed={rmImage}
          onFile={(f) => { setImage(f); if (f) setRmImage(false) }} onRemove={() => setRmImage(true)}
        />
        <FilePick
          label={t('campaign.lore.audio')} pick={t('campaign.lore.pick_audio')} accept="audio/*"
          file={audio} existing={!!lore?.has_audio} removed={rmAudio}
          onFile={(f) => { setAudio(f); if (f) setRmAudio(false) }} onRemove={() => setRmAudio(true)}
        />
        <div className="flex gap-2 pt-1">
          <Button variant="secondary" fullWidth onClick={onClose}>{t('common.cancel')}</Button>
          <Button fullWidth disabled={!title.trim()} loading={save.isPending} onClick={() => save.mutate()}>{t('common.save')}</Button>
        </div>
      </div>
    </Sheet>
  )
}

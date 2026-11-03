import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import Sheet from '@/components/ui/Sheet'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import { api, ApiError } from '@/api/client'
import { downscaleImage } from '@/lib/downscaleImage'
import { useToast } from '@/hooks/useToast'

interface Props { open: boolean; campaignId: number; onClose: () => void }

/** Il master carica una nuova mappa: nome + immagine (ridotta prima dell'invio). */
export default function MapUploadSheet({ open, campaignId, onClose }: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const ref = useRef<HTMLInputElement>(null)
  const [name, setName] = useState('')
  const [file, setFile] = useState<File | null>(null)

  useEffect(() => { if (open) { setName(''); setFile(null) } }, [open])

  const save = useMutation({
    mutationFn: async () => {
      let small: File
      try {
        small = await downscaleImage(file!)
      } catch {
        throw new Error('decode')
      }
      const fd = new FormData()
      fd.append('name', name.trim())
      fd.append('file', small)
      return api.atlas.uploadMap(campaignId, fd)
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['atlas-maps', campaignId] }); onClose() },
    onError: (e) => toast.error(t(
      e instanceof ApiError
        ? (e.status === 400 ? 'atlas.err_upload' : 'common.action_failed')
        : e.message === 'decode' ? 'atlas.err_image' : 'common.action_failed',
    )),
  })

  return (
    <Sheet open={open} onClose={onClose} title={t('atlas.new_title')}>
      <div className="p-5 space-y-3">
        <Input label={t('atlas.name_label')} value={name} onChange={(v: string) => setName(v.slice(0, 80))} />
        <div className="flex flex-wrap items-center gap-2">
          <input ref={ref} type="file" accept="image/png,image/jpeg,image/webp" className="hidden"
            onChange={(e) => { setFile(e.target.files?.[0] ?? null); e.target.value = '' }} />
          <Button variant="secondary" size="sm" onClick={() => ref.current?.click()}>{t('atlas.pick_image')}</Button>
          {file && <span className="min-w-0 break-all text-xs text-dnd-text-muted font-body">{file.name}</span>}
        </div>
        <div className="flex gap-2 pt-1">
          <Button variant="secondary" fullWidth onClick={onClose}>{t('common.cancel')}</Button>
          <Button fullWidth disabled={!name.trim() || !file} loading={save.isPending} onClick={() => save.mutate()}>{t('common.save')}</Button>
        </div>
      </div>
    </Sheet>
  )
}

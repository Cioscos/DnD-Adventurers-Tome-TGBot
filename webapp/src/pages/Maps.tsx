import { useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import { haptic } from '@/auth/telegram'

export default function Maps() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null)
  const [expanded, setExpanded] = useState<number | null>(null)

  // Upload form state
  const [showUpload, setShowUpload] = useState(false)
  const [zoneName, setZoneName] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
  })

  const deleteMutation = useMutation({
    mutationFn: (mapId: number) => api.maps.remove(charId, mapId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      setDeleteTarget(null)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const uploadMutation = useMutation({
    mutationFn: ({ zone, file }: { zone: string; file: File }) =>
      api.maps.upload(charId, zone, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      setShowUpload(false)
      setZoneName('')
      setSelectedFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const handleUpload = () => {
    if (!zoneName.trim() || !selectedFile) return
    uploadMutation.mutate({ zone: zoneName.trim(), file: selectedFile })
  }

  if (!char) return null

  const maps = char.maps ?? []

  // Group by zone
  const zones = maps.reduce<Record<string, typeof maps>>((acc, m) => {
    if (!acc[m.zone_name]) acc[m.zone_name] = []
    acc[m.zone_name].push(m)
    return acc
  }, {})

  // Collect existing zone names for quick-select
  const existingZones = Object.keys(zones)

  return (
    <Layout title={t('character.maps.title')} backTo={`/char/${charId}`}>
      {/* Add map button */}
      <button
        onClick={() => setShowUpload(!showUpload)}
        className="w-full py-3 rounded-2xl bg-[var(--tg-theme-button-color)]
                   text-[var(--tg-theme-button-text-color)] font-semibold active:opacity-80"
      >
        + {t('character.maps.add_map')}
      </button>

      {/* Upload form */}
      {showUpload && (
        <Card className="space-y-3">
          <div>
            <label className="block text-sm text-[var(--tg-theme-hint-color)] mb-1">
              {t('character.maps.zone_name')}
            </label>
            <input
              type="text"
              value={zoneName}
              onChange={(e) => setZoneName(e.target.value)}
              placeholder={t('character.maps.zone_name_placeholder')}
              className="w-full bg-white/10 rounded-xl px-3 py-2 text-sm outline-none
                         focus:ring-2 focus:ring-[var(--tg-theme-button-color)]"
            />
          </div>

          {/* Quick-select existing zones */}
          {existingZones.length > 0 && (
            <div className="flex gap-1 flex-wrap">
              {existingZones.map((z) => (
                <button
                  key={z}
                  onClick={() => setZoneName(z)}
                  className={`px-2 py-1 rounded-lg text-xs ${
                    zoneName === z ? 'bg-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-text-color)]' : 'bg-white/10'
                  }`}
                >
                  {z}
                </button>
              ))}
            </div>
          )}

          <div>
            <label className="block text-sm text-[var(--tg-theme-hint-color)] mb-1">
              {t('character.maps.select_file')}
            </label>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*,.pdf"
              onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
              className="w-full text-sm file:mr-3 file:py-1.5 file:px-3 file:rounded-lg
                         file:border-0 file:text-sm file:font-medium
                         file:bg-white/10 file:text-[var(--tg-theme-text-color)]"
            />
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleUpload}
              disabled={!zoneName.trim() || !selectedFile || uploadMutation.isPending}
              className="flex-1 py-2.5 rounded-xl bg-[var(--tg-theme-button-color)]
                         text-[var(--tg-theme-button-text-color)] font-semibold
                         disabled:opacity-40 active:opacity-80"
            >
              {uploadMutation.isPending ? '...' : t('character.maps.upload_btn')}
            </button>
            <button
              onClick={() => {
                setShowUpload(false)
                setZoneName('')
                setSelectedFile(null)
                if (fileInputRef.current) fileInputRef.current.value = ''
              }}
              className="flex-1 py-2.5 rounded-xl bg-white/10"
            >
              {t('common.cancel')}
            </button>
          </div>
        </Card>
      )}

      {maps.length === 0 && !showUpload ? (
        <Card>
          <p className="text-center text-[var(--tg-theme-hint-color)]">{t('common.none')}</p>
        </Card>
      ) : (
        Object.entries(zones).map(([zone, zoneMaps]) => (
          <div key={zone}>
            <p className="text-sm font-semibold text-[var(--tg-theme-hint-color)] px-1 mb-1">
              📍 {zone}
            </p>
            {zoneMaps.map((m) => (
              <Card key={m.id} className="mb-2">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">{m.file_type.toUpperCase()}</span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setExpanded(expanded === m.id ? null : m.id)}
                      className="text-xs text-[var(--tg-theme-link-color)]"
                    >
                      {expanded === m.id ? t('common.close') : t('character.maps.open')}
                    </button>
                    <button
                      onClick={() => setDeleteTarget(m.id)}
                      className="text-xs text-red-400"
                    >
                      {t('common.delete')}
                    </button>
                  </div>
                </div>

                {expanded === m.id && (
                  <img
                    src={api.maps.fileUrl(charId, m.id)}
                    alt={zone}
                    className="w-full rounded-lg"
                    loading="lazy"
                  />
                )}
              </Card>
            ))}
          </div>
        ))
      )}

      {deleteTarget !== null && (
        <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4">
          <Card className="w-full">
            <p className="text-sm text-center mb-3">
              {t('character.maps.delete_confirm', {
                zone: maps.find((m) => m.id === deleteTarget)?.zone_name ?? '',
              })}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => deleteMutation.mutate(deleteTarget)}
                className="flex-1 py-2 rounded-xl bg-red-500/80 text-white font-medium"
              >
                {t('common.delete')}
              </button>
              <button
                onClick={() => setDeleteTarget(null)}
                className="flex-1 py-2 rounded-xl bg-white/10 font-medium"
              >
                {t('common.cancel')}
              </button>
            </div>
          </Card>
        </div>
      )}
    </Layout>
  )
}

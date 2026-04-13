import { useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import { haptic } from '@/auth/telegram'
import type { MapEntry } from '@/types'

export default function Maps() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()

  // Overlay
  const [overlayMap, setOverlayMap] = useState<MapEntry | null>(null)

  // Delete targets
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; zone: string } | null>(null)
  const [deleteZoneTarget, setDeleteZoneTarget] = useState<string | null>(null)

  // Upload form
  const [showUpload, setShowUpload] = useState(false)
  const [zoneName, setZoneName] = useState('')
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)
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

  const deleteZoneMutation = useMutation({
    mutationFn: (zone: string) => api.maps.removeZone(charId, zone),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['character', charId] })
      setDeleteZoneTarget(null)
      haptic.success()
    },
    onError: () => haptic.error(),
  })

  const handleUpload = async () => {
    if (!zoneName.trim() || selectedFiles.length === 0) return
    setIsUploading(true)
    setUploadError(null)
    try {
      for (const file of selectedFiles) {
        await api.maps.upload(charId, zoneName.trim(), file)
      }
      await qc.invalidateQueries({ queryKey: ['character', charId] })
      setShowUpload(false)
      setZoneName('')
      setSelectedFiles([])
      if (fileInputRef.current) fileInputRef.current.value = ''
      haptic.success()
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed')
      haptic.error()
    } finally {
      setIsUploading(false)
    }
  }

  const openUploadForZone = (zone: string) => {
    setZoneName(zone)
    setShowUpload(true)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  if (!char) return null

  const maps = char.maps ?? []

  const zones = maps.reduce<Record<string, MapEntry[]>>((acc, m) => {
    if (!acc[m.zone_name]) acc[m.zone_name] = []
    acc[m.zone_name].push(m)
    return acc
  }, {})

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

          {existingZones.length > 0 && (
            <div className="flex gap-1 flex-wrap">
              {existingZones.map((z) => (
                <button
                  key={z}
                  onClick={() => setZoneName(z)}
                  className={`px-2 py-1 rounded-lg text-xs ${
                    zoneName === z
                      ? 'bg-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-text-color)]'
                      : 'bg-white/10'
                  }`}
                >
                  {z}
                </button>
              ))}
            </div>
          )}

          <div>
            <label className="block text-sm text-[var(--tg-theme-hint-color)] mb-1">
              {t('character.maps.select_files')}
            </label>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/*,.pdf,.heic,.heif"
              onChange={(e) => setSelectedFiles(Array.from(e.target.files ?? []))}
              className="w-full text-sm file:mr-3 file:py-1.5 file:px-3 file:rounded-lg
                         file:border-0 file:text-sm file:font-medium
                         file:bg-white/10 file:text-[var(--tg-theme-text-color)]"
            />
            {selectedFiles.length > 1 && (
              <p className="text-xs text-[var(--tg-theme-hint-color)] mt-1">
                {t('character.maps.files_selected', { count: selectedFiles.length })}
              </p>
            )}
          </div>

          {uploadError && (
            <p className="text-sm text-red-400 bg-red-500/10 rounded-xl px-3 py-2">{uploadError}</p>
          )}

          <div className="flex gap-2">
            <button
              onClick={handleUpload}
              disabled={!zoneName.trim() || selectedFiles.length === 0 || isUploading}
              className="flex-1 py-2.5 rounded-xl bg-[var(--tg-theme-button-color)]
                         text-[var(--tg-theme-button-text-color)] font-semibold
                         disabled:opacity-40 active:opacity-80"
            >
              {isUploading ? '...' : t('character.maps.upload_btn')}
            </button>
            <button
              onClick={() => {
                setShowUpload(false)
                setZoneName('')
                setSelectedFiles([])
                if (fileInputRef.current) fileInputRef.current.value = ''
              }}
              className="flex-1 py-2.5 rounded-xl bg-white/10"
            >
              {t('common.cancel')}
            </button>
          </div>
        </Card>
      )}

      {/* Zone list */}
      {maps.length === 0 && !showUpload ? (
        <Card>
          <p className="text-center text-[var(--tg-theme-hint-color)]">{t('common.none')}</p>
        </Card>
      ) : (
        Object.entries(zones).map(([zone, zoneMaps]) => (
          <div key={zone} className="mb-4">
            {/* Zone header */}
            <div className="flex items-center justify-between px-1 mb-2">
              <p className="text-sm font-semibold text-[var(--tg-theme-hint-color)]">
                📍 {zone}
                <span className="ml-1.5 font-normal opacity-70">({zoneMaps.length})</span>
              </p>
              <div className="flex gap-3 items-center">
                <button
                  onClick={() => openUploadForZone(zone)}
                  className="text-xs text-[var(--tg-theme-link-color)]"
                >
                  + {t('character.maps.add_more')}
                </button>
                <button
                  onClick={() => setDeleteZoneTarget(zone)}
                  className="text-xs text-red-400"
                >
                  {t('character.maps.delete_zone')}
                </button>
              </div>
            </div>

            {/* Thumbnail grid */}
            <div className="grid grid-cols-3 gap-1.5">
              {zoneMaps.map((m) => (
                <div
                  key={m.id}
                  className="relative aspect-square rounded-xl overflow-hidden bg-white/5 cursor-pointer active:opacity-80"
                >
                  {m.file_type === 'photo' ? (
                    <img
                      src={api.maps.fileUrl(charId, m.id)}
                      alt={zone}
                      className="w-full h-full object-cover"
                      loading="lazy"
                      onClick={() => setOverlayMap(m)}
                    />
                  ) : (
                    <div
                      className="w-full h-full flex flex-col items-center justify-center
                                 text-[var(--tg-theme-hint-color)]"
                      onClick={() => setOverlayMap(m)}
                    >
                      <span className="text-3xl">📄</span>
                      <span className="text-xs mt-1 uppercase opacity-60">{m.file_type}</span>
                    </div>
                  )}
                  {/* Per-file delete button */}
                  <button
                    onClick={(e) => { e.stopPropagation(); setDeleteTarget({ id: m.id, zone }) }}
                    className="absolute top-1 right-1 w-5 h-5 rounded-full bg-black/60 text-white
                               text-xs flex items-center justify-center leading-none"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>
        ))
      )}

      {/* Full-screen overlay */}
      {overlayMap && (
        <div
          className="fixed inset-0 bg-black/90 z-50 flex flex-col"
          onClick={() => setOverlayMap(null)}
        >
          <div className="flex justify-end p-4 shrink-0">
            <button
              onClick={() => setOverlayMap(null)}
              className="text-white text-lg w-9 h-9 flex items-center justify-center
                         rounded-full bg-white/20"
            >
              ✕
            </button>
          </div>
          <div
            className="flex-1 flex items-center justify-center p-4 overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {overlayMap.file_type === 'photo' ? (
              <img
                src={api.maps.fileUrl(charId, overlayMap.id)}
                alt={overlayMap.zone_name}
                className="max-w-full max-h-full rounded-xl object-contain"
              />
            ) : (
              <div className="text-center text-white space-y-4">
                <div className="text-6xl">📄</div>
                <p className="text-sm opacity-70">{overlayMap.zone_name}</p>
                <a
                  href={api.maps.fileUrl(charId, overlayMap.id)}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-block px-4 py-2 rounded-xl
                             bg-[var(--tg-theme-button-color)]
                             text-[var(--tg-theme-button-text-color)] text-sm font-medium"
                  onClick={(e) => e.stopPropagation()}
                >
                  {t('character.maps.open_file')}
                </a>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Delete single file confirm */}
      {deleteTarget !== null && (
        <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4">
          <Card className="w-full">
            <p className="text-sm text-center mb-3">
              {t('character.maps.delete_file_confirm', { zone: deleteTarget.zone })}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => deleteMutation.mutate(deleteTarget.id)}
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

      {/* Delete entire zone confirm */}
      {deleteZoneTarget !== null && (
        <div className="fixed inset-0 bg-black/60 flex items-end z-50 p-4">
          <Card className="w-full">
            <p className="text-sm text-center mb-3">
              {t('character.maps.delete_zone_confirm', { zone: deleteZoneTarget })}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => deleteZoneMutation.mutate(deleteZoneTarget)}
                className="flex-1 py-2 rounded-xl bg-red-500/80 text-white font-medium"
              >
                {t('common.delete')}
              </button>
              <button
                onClick={() => setDeleteZoneTarget(null)}
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

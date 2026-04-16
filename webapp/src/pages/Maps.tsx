import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Card from '@/components/Card'
import DndButton from '@/components/DndButton'
import { haptic } from '@/auth/telegram'
import { X } from 'lucide-react'
import MapUploadForm from '@/pages/maps/MapUploadForm'
import MapZoneGroup from '@/pages/maps/MapZoneGroup'
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
  const [uploadInitialZone, setUploadInitialZone] = useState('')

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

  const openUploadForZone = (zone: string) => {
    setUploadInitialZone(zone)
    setShowUpload(true)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleUploadComplete = () => {
    qc.invalidateQueries({ queryKey: ['character', charId] })
    setShowUpload(false)
    setUploadInitialZone('')
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
    <Layout title={t('character.maps.title')} backTo={`/char/${charId}`} group="tools" page="maps">
      {/* Add map button */}
      <DndButton
        onClick={() => {
          setUploadInitialZone('')
          setShowUpload(!showUpload)
        }}
        className="w-full"
      >
        + {t('character.maps.add_map')}
      </DndButton>

      {/* Upload form */}
      {showUpload && (
        <MapUploadForm
          charId={charId}
          existingZones={existingZones}
          onUploadComplete={handleUploadComplete}
          onCancel={() => {
            setShowUpload(false)
            setUploadInitialZone('')
          }}
          initialZone={uploadInitialZone}
        />
      )}

      {/* Zone list */}
      {maps.length === 0 && !showUpload ? (
        <Card>
          <p className="text-center text-dnd-text-secondary">{t('common.none')}</p>
        </Card>
      ) : (
        Object.entries(zones).map(([zone, zoneMaps]) => (
          <MapZoneGroup
            key={zone}
            charId={charId}
            zoneName={zone}
            maps={zoneMaps}
            onAddMore={openUploadForZone}
            onDeleteFile={(mapId, z) => setDeleteTarget({ id: mapId, zone: z })}
            onDeleteZone={(z) => setDeleteZoneTarget(z)}
            onPreview={(m) => setOverlayMap(m)}
          />
        ))
      )}

      {/* Full-screen overlay */}
      {overlayMap && (
        <div
          className="fixed inset-0 bg-black/90 z-50 flex flex-col"
          onClick={() => setOverlayMap(null)}
        >
          <div className="flex justify-end p-4 pt-safe shrink-0">
            <button
              onClick={(e) => { e.stopPropagation(); setOverlayMap(null) }}
              className="w-11 h-11 flex items-center justify-center
                         rounded-full bg-white/20 border border-white/40 backdrop-blur-sm"
            >
              <X size={22} className="text-white" />
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
                             bg-dnd-gold text-dnd-bg text-sm font-medium"
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
              <DndButton
                variant="danger"
                onClick={() => deleteMutation.mutate(deleteTarget.id)}
                loading={deleteMutation.isPending}
                className="flex-1"
              >
                {t('common.delete')}
              </DndButton>
              <DndButton
                variant="secondary"
                onClick={() => setDeleteTarget(null)}
                className="flex-1"
              >
                {t('common.cancel')}
              </DndButton>
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
              <DndButton
                variant="danger"
                onClick={() => deleteZoneMutation.mutate(deleteZoneTarget)}
                loading={deleteZoneMutation.isPending}
                className="flex-1"
              >
                {t('common.delete')}
              </DndButton>
              <DndButton
                variant="secondary"
                onClick={() => setDeleteZoneTarget(null)}
                className="flex-1"
              >
                {t('common.cancel')}
              </DndButton>
            </div>
          </Card>
        </div>
      )}
    </Layout>
  )
}

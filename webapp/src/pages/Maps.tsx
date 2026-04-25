import { useState } from 'react'
import { createPortal } from 'react-dom'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { X, Plus, FileText } from 'lucide-react'
import { GiTreasureMap as MapIcon } from 'react-icons/gi'
import { api } from '@/api/client'
import Layout from '@/components/Layout'
import Surface from '@/components/ui/Surface'
import Button from '@/components/ui/Button'
import Sheet from '@/components/ui/Sheet'
import { haptic } from '@/auth/telegram'
import MapUploadForm from '@/pages/maps/MapUploadForm'
import MapZoneGroup from '@/pages/maps/MapZoneGroup'
import type { MapEntry } from '@/types'

export default function Maps() {
  const { id } = useParams<{ id: string }>()
  const charId = Number(id)
  const { t } = useTranslation()
  const qc = useQueryClient()

  const [overlayMap, setOverlayMap] = useState<MapEntry | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; zone: string } | null>(null)
  const [deleteZoneTarget, setDeleteZoneTarget] = useState<string | null>(null)
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
      <Button
        variant="primary"
        size="lg"
        fullWidth
        onClick={() => {
          setUploadInitialZone('')
          setShowUpload(!showUpload)
        }}
        icon={<Plus size={18} />}
        haptic="medium"
      >
        {t('character.maps.add_map')}
      </Button>

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

      {maps.length === 0 && !showUpload ? (
        <Surface variant="flat" className="text-center py-8">
          <MapIcon className="mx-auto text-dnd-text-faint mb-2" size={32} />
          <p className="text-dnd-text-muted font-body italic">{t('common.none')}</p>
        </Surface>
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

      {/* Full-screen overlay — portaled to body to escape Layout stacking context */}
      {createPortal(
        <AnimatePresence>
          {overlayMap && (
            <m.div
              className="fixed inset-0 z-[9999] flex flex-col"
              style={{ background: 'rgba(5, 5, 8, 0.98)' }}
              onClick={() => setOverlayMap(null)}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <div className="flex justify-end p-4 pt-safe shrink-0 relative z-10">
                <m.button
                  onClick={(e) => { e.stopPropagation(); setOverlayMap(null) }}
                  className="w-12 h-12 flex items-center justify-center rounded-full
                             bg-gradient-gold text-dnd-ink border-2 border-dnd-gold-bright
                             shadow-[0_0_20px_var(--dnd-gold-glow)]"
                  whileTap={{ scale: 0.9 }}
                  aria-label="Close"
                >
                  <X size={24} strokeWidth={3} />
                </m.button>
              </div>
              <div
                className="flex-1 flex items-center justify-center p-4 overflow-auto"
                onClick={(e) => e.stopPropagation()}
              >
                {overlayMap.file_type === 'photo' ? (
                  <m.img
                    src={api.maps.fileUrl(charId, overlayMap.id)}
                    alt={overlayMap.zone_name}
                    className="max-w-full max-h-full rounded-xl object-contain shadow-parchment-2xl"
                    initial={{ scale: 0.95, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ duration: 0.3 }}
                  />
                ) : (
                  <div className="text-center text-white space-y-4">
                    <FileText size={80} className="mx-auto text-dnd-gold-bright" />
                    <p className="text-sm opacity-70 font-body">{overlayMap.zone_name}</p>
                    <a
                      href={api.maps.fileUrl(charId, overlayMap.id)}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-block px-4 py-2 rounded-xl bg-gradient-gold text-dnd-ink text-sm font-cinzel uppercase tracking-wider shadow-engrave"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {t('character.maps.open_file')}
                    </a>
                  </div>
                )}
              </div>
            </m.div>
          )}
        </AnimatePresence>,
        document.body
      )}

      {/* Delete single file confirm */}
      <Sheet
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        centered
        title={t('common.confirm')}
      >
        <div className="p-5 space-y-3">
          <p className="text-sm text-center text-dnd-text font-body">
            {deleteTarget && t('character.maps.delete_file_confirm', { zone: deleteTarget.zone })}
          </p>
          <div className="flex gap-2">
            <Button
              variant="danger"
              fullWidth
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
              loading={deleteMutation.isPending}
              haptic="error"
            >
              {t('common.delete')}
            </Button>
            <Button variant="secondary" fullWidth onClick={() => setDeleteTarget(null)}>
              {t('common.cancel')}
            </Button>
          </div>
        </div>
      </Sheet>

      {/* Delete entire zone confirm */}
      <Sheet
        open={deleteZoneTarget !== null}
        onClose={() => setDeleteZoneTarget(null)}
        centered
        title={t('common.confirm')}
      >
        <div className="p-5 space-y-3">
          <p className="text-sm text-center text-dnd-text font-body">
            {deleteZoneTarget && t('character.maps.delete_zone_confirm', { zone: deleteZoneTarget })}
          </p>
          <div className="flex gap-2">
            <Button
              variant="danger"
              fullWidth
              onClick={() => deleteZoneTarget && deleteZoneMutation.mutate(deleteZoneTarget)}
              loading={deleteZoneMutation.isPending}
              haptic="error"
            >
              {t('common.delete')}
            </Button>
            <Button variant="secondary" fullWidth onClick={() => setDeleteZoneTarget(null)}>
              {t('common.cancel')}
            </Button>
          </div>
        </div>
      </Sheet>
    </Layout>
  )
}

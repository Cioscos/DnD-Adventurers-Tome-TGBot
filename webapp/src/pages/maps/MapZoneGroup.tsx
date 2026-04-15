import React from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import type { MapEntry } from '@/types'

interface MapZoneGroupProps {
  charId: number
  zoneName: string
  maps: MapEntry[]
  onAddMore: (zone: string) => void
  onDeleteFile: (id: number, zone: string) => void
  onDeleteZone: (zone: string) => void
  onPreview: (map: MapEntry) => void
}

function MapZoneGroupInner({
  charId,
  zoneName,
  maps,
  onAddMore,
  onDeleteFile,
  onDeleteZone,
  onPreview,
}: MapZoneGroupProps) {
  const { t } = useTranslation()

  return (
    <div className="mb-4">
      {/* Zone header */}
      <div className="flex items-center justify-between px-1 mb-2">
        <p className="text-sm font-semibold text-dnd-text-secondary">
          {zoneName}
          <span className="ml-1.5 font-normal opacity-70">({maps.length})</span>
        </p>
        <div className="flex gap-3 items-center">
          <button
            onClick={() => onAddMore(zoneName)}
            className="text-xs text-dnd-gold-dim"
          >
            + {t('character.maps.add_more')}
          </button>
          <button
            onClick={() => onDeleteZone(zoneName)}
            className="text-xs text-[var(--dnd-danger)]"
          >
            {t('character.maps.delete_zone')}
          </button>
        </div>
      </div>

      {/* Thumbnail grid */}
      <div className="grid grid-cols-3 gap-1.5">
        {maps.map((m) => (
          <div
            key={m.id}
            className="relative aspect-square rounded-xl overflow-hidden bg-dnd-surface cursor-pointer active:opacity-80"
          >
            {m.file_type === 'photo' ? (
              <img
                src={api.maps.fileUrl(charId, m.id)}
                alt={zoneName}
                className="w-full h-full object-cover"
                loading="lazy"
                onClick={() => onPreview(m)}
              />
            ) : (
              <div
                className="w-full h-full flex flex-col items-center justify-center text-dnd-text-secondary"
                onClick={() => onPreview(m)}
              >
                <span className="text-3xl">📄</span>
                <span className="text-xs mt-1 uppercase opacity-60">{m.file_type}</span>
              </div>
            )}
            {/* Per-file delete button */}
            <button
              onClick={(e) => { e.stopPropagation(); onDeleteFile(m.id, zoneName) }}
              className="absolute top-1 right-1 w-5 h-5 rounded-full bg-black/60 text-white
                         text-xs flex items-center justify-center leading-none"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

const MapZoneGroup = React.memo(MapZoneGroupInner)
export default MapZoneGroup

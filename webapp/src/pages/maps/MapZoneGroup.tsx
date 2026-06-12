import React, { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { X, FileText } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import type { CharacterFull, MapEntry } from '@/types'
import { haptic } from '@/auth/telegram'

interface MapZoneGroupProps {
  charId: number
  zoneName: string
  maps: MapEntry[]
  onAddMore: (zone: string) => void
  onDeleteFile: (id: number, zone: string) => void
  onDeleteZone: (zone: string) => void
  onPreview: (map: MapEntry) => void
}

function sameIds(a: number[], b: number[]): boolean {
  if (a.length !== b.length) return false
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false
  return true
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
  const qc = useQueryClient()

  const serverIds = maps.map((m) => m.id)
  const [localOrder, setLocalOrder] = useState<number[]>(serverIds)
  const lastServerIdsRef = useRef<number[]>(serverIds)
  const dragIdRef = useRef<number | null>(null)
  const [draggingId, setDraggingId] = useState<number | null>(null)

  useEffect(() => {
    if (!sameIds(serverIds, lastServerIdsRef.current)) {
      setLocalOrder(serverIds)
      lastServerIdsRef.current = serverIds
    }
  }, [serverIds])

  const byId = new Map(maps.map((m) => [m.id, m]))
  const ordered: MapEntry[] = []
  for (const id of localOrder) {
    const m = byId.get(id)
    if (m) ordered.push(m)
  }

  const reorderMutation = useMutation({
    mutationFn: (order: number[]) => api.maps.reorder(charId, zoneName, order),
    onMutate: async (order) => {
      await qc.cancelQueries({ queryKey: ['character', charId] })
      const previous = qc.getQueryData<CharacterFull>(['character', charId])
      qc.setQueryData<CharacterFull>(['character', charId], (prev) => {
        if (!prev) return prev
        const otherMaps = (prev.maps ?? []).filter((m) => m.zone_name !== zoneName)
        const zoneMaps = (prev.maps ?? []).filter((m) => m.zone_name === zoneName)
        const zoneById = new Map(zoneMaps.map((m) => [m.id, m]))
        const newZoneMaps: MapEntry[] = []
        order.forEach((id, idx) => {
          const m = zoneById.get(id)
          if (m) newZoneMaps.push({ ...m, position: idx })
        })
        return { ...prev, maps: [...otherMaps, ...newZoneMaps] }
      })
      return { previous }
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.previous) qc.setQueryData(['character', charId], ctx.previous)
      haptic.error()
      qc.invalidateQueries({ queryKey: ['character', charId] })
    },
    onSuccess: (data) => {
      qc.setQueryData(['character', charId], data)
      haptic.light()
    },
  })

  const handleDragStart = (id: number) => (e: React.DragEvent<HTMLDivElement>) => {
    dragIdRef.current = id
    setDraggingId(id)
    try {
      e.dataTransfer.effectAllowed = 'move'
      e.dataTransfer.setData('text/plain', String(id))
    } catch {
      /* Safari quirks */
    }
  }

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }

  const handleDrop = (targetId: number) => (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    const fromId = dragIdRef.current
    dragIdRef.current = null
    setDraggingId(null)
    if (fromId === null || fromId === targetId) return
    const next = [...localOrder]
    const fromIdx = next.indexOf(fromId)
    const toIdx = next.indexOf(targetId)
    if (fromIdx < 0 || toIdx < 0) return
    next.splice(fromIdx, 1)
    next.splice(toIdx, 0, fromId)
    setLocalOrder(next)
    reorderMutation.mutate(next)
  }

  const handleDragEnd = () => {
    dragIdRef.current = null
    setDraggingId(null)
  }

  const isReorderable = maps.length >= 2

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between px-1 mb-2">
        <p className="text-sm font-semibold text-dnd-text-muted">
          {zoneName}
          <span className="ml-1.5 font-normal opacity-70">({maps.length})</span>
        </p>
        <div className="flex gap-1 items-center">
          <button
            onClick={() => onAddMore(zoneName)}
            className="min-h-[44px] px-2 text-xs text-dnd-gold-dim hover:text-dnd-gold-bright transition-colors"
          >
            + {t('character.maps.add_more')}
          </button>
          <button
            onClick={() => onDeleteZone(zoneName)}
            className="min-h-[44px] px-2 text-xs text-dnd-crimson-bright transition-colors"
          >
            {t('character.maps.delete_zone')}
          </button>
        </div>
      </div>

      {isReorderable && (
        <p className="px-1 mb-1.5 text-[10px] uppercase tracking-widest text-dnd-text-faint italic">
          {t('character.maps.reorder_hint')}
        </p>
      )}

      <div className="grid grid-cols-3 gap-1.5">
        {ordered.map((m) => (
          <div
            key={m.id}
            draggable={isReorderable}
            onDragStart={isReorderable ? handleDragStart(m.id) : undefined}
            onDragOver={isReorderable ? handleDragOver : undefined}
            onDrop={isReorderable ? handleDrop(m.id) : undefined}
            onDragEnd={isReorderable ? handleDragEnd : undefined}
            className={`relative aspect-square rounded-xl overflow-hidden bg-dnd-surface border border-dnd-gold-dim/40 shadow-parchment-md active:opacity-80 transition-all hover:border-dnd-gold/70 ${
              isReorderable ? 'cursor-grab active:cursor-grabbing' : 'cursor-pointer'
            } ${draggingId === m.id ? 'opacity-40' : ''}`}
          >
            {m.file_type === 'photo' ? (
              <img
                src={api.maps.fileUrl(charId, m.id)}
                alt={zoneName}
                className="w-full h-full object-cover pointer-events-none"
                loading="lazy"
                draggable={false}
              />
            ) : (
              <div className="w-full h-full flex flex-col items-center justify-center text-dnd-text-muted pointer-events-none">
                <FileText size={30} className="text-dnd-gold-dim" />
                <span className="text-xs mt-1 uppercase opacity-60">{m.file_type}</span>
              </div>
            )}
            {/* Click overlay (under delete button) — drag handlers live on the wrapper */}
            <button
              type="button"
              onClick={() => onPreview(m)}
              className="absolute inset-0 w-full h-full"
              aria-label={zoneName}
            />
            <button
              onClick={(e) => { e.stopPropagation(); onDeleteFile(m.id, zoneName) }}
              className="absolute top-1 right-1 w-10 h-10 rounded-full bg-dnd-ink/80 text-dnd-text flex items-center justify-center z-10"
              aria-label={t('common.delete')}
            >
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

const MapZoneGroup = React.memo(MapZoneGroupInner)
export default MapZoneGroup

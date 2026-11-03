import { useRef } from 'react'
import { useTranslation } from 'react-i18next'
import Pressable from '@/components/ui/Pressable'
import { resolveType } from '@/lib/atlasIcons'
import type { AtlasMarker } from '@/types'

interface Props {
  marker: AtlasMarker
  scale: number
  selected: boolean
  /** Il master vede i suoi marker nascosti: semitrasparenti e tratteggiati. */
  isGm: boolean
  onSelect: (id: number) => void
}

/** Goccia ancorata alla punta in (x, y); scala inversa allo zoom, così resta della stessa grandezza. */
export default function MarkerPin({ marker, scale, selected, isGm, onSelect }: Props) {
  const { t } = useTranslation()
  const { Icon, color, label } = resolveType(marker.type)
  const hidden = isGm && marker.visibility === 'private'
  const down = useRef<{ x: number; y: number } | null>(null)
  const border = marker.author_role === 'player' ? 'border-dashed border-dnd-text' : hidden ? 'border-dashed border-current' : 'border-current'

  return (
    // Il div porta posizione e scala inversa; il Pressable dentro è l'area toccabile 44×44.
    <div
      data-pin={marker.id}
      data-layout-ok="posizione scelta da chi segna il luogo: i marker vicini si separano con lo zoom"
      data-hidden={hidden}
      data-selected={selected}
      className={`absolute h-11 w-11 ${selected ? 'z-20' : 'z-10'} ${hidden ? 'opacity-[0.45]' : ''}`}
      style={{
        left: `${marker.x * 100}%`,
        top: `${marker.y * 100}%`,
        transform: `translate(-50%,-100%) scale(${1 / scale})`,
        transformOrigin: 'bottom center',
      }}
    >
      <Pressable
        aria-label={`${label(t)}: ${marker.name}`}
        aria-pressed={selected}
        className="flex h-11 w-11 items-end justify-center"
        onPointerDown={(e) => { down.current = { x: e.clientX, y: e.clientY } }}
        onClick={(e) => {
          e.stopPropagation()
          // Il pan può partire sopra un marker: se il dito si è spostato non è un tap.
          const d = down.current
          if (d && Math.hypot(e.clientX - d.x, e.clientY - d.y) > 10) return
          onSelect(marker.id)
        }}
      >
        {/* Quadrato ruotato con un angolo vivo = goccia con la punta in basso, sul punto (x, y). */}
        <span
          className={`mb-[6px] flex h-7 w-7 rotate-45 items-center justify-center rounded-[50%_50%_0_50%] border-2 bg-dnd-surface-raised ${color} ${border} ${selected ? 'shadow-halo-gold' : 'shadow-parchment-md'}`}
        >
          <Icon size={14} className={`-rotate-45 ${color}`} aria-hidden />
        </span>
      </Pressable>
      {(selected || scale >= 1.5) && (
        <span className="pointer-events-none absolute bottom-full left-1/2 max-w-[10rem] -translate-x-1/2 truncate rounded-md border border-dnd-border bg-dnd-surface-raised/90 px-2 py-0.5 text-xs font-body text-dnd-text shadow-parchment-md">
          {marker.name}
        </span>
      )}
    </div>
  )
}

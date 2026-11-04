import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { ChevronLeft, MapPinPlus, Settings2 } from 'lucide-react'
import Pressable from '@/components/ui/Pressable'
import Button from '@/components/ui/Button'
import FilterChip from '@/components/ui/FilterChip'
import Skeleton from '@/components/ui/Skeleton'
import MapCanvas, { type MapCanvasHandle } from '@/pages/atlas/MapCanvas'
import MapManageSheet from '@/pages/atlas/MapManageSheet'
import MarkerSheet from '@/pages/atlas/MarkerSheet'
import MarkerFormSheet from '@/pages/atlas/MarkerFormSheet'
import PlaceOverlay from '@/pages/atlas/PlaceOverlay'
import { useToast } from '@/hooks/useToast'
import { usePageBack } from '@/hooks/useOverlayDismiss'
import { api, ApiError } from '@/api/client'
import type { AtlasMarker } from '@/types'

type Filter = 'all' | 'gm' | 'group' | 'mine'
/** view = navigazione; place = mirino per un nuovo marker; move = mirino per spostare il marker id (Task 7). */
export type AtlasMode = 'view' | 'place' | { move: number }
export interface TrailEntry { id: number; name: string }

const FILTERS: Record<Filter, (m: AtlasMarker) => boolean> = {
  all: () => true,
  gm: (m) => m.author_role === 'gm',
  group: (m) => m.author_role === 'player' && !m.mine,
  mine: (m) => m.mine,
}
const notFound = (e: unknown) => e instanceof ApiError && (e.status === 404 || e.status === 403)

/** Una istanza per mappa: aprendo una sottomappa cambia solo il param, e zoom, selezione,
 *  filtro, modo e deep link della mappa precedente non devono restare. */
export default function AtlasMap() {
  const { mapId } = useParams<{ mapId: string }>()
  return <AtlasMapView key={mapId} />
}

/** Schermo della mappa dell'atlante: pan/zoom, marker, filtri, percorso tra sottomappe. */
function AtlasMapView() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { id, mapId } = useParams<{ id: string; mapId: string }>()
  const campId = Number(id)
  const mId = Number(mapId)
  const state = (useLocation().state ?? {}) as { trail?: TrailEntry[]; from?: string }
  const trail = state.trail ?? []
  const [params] = useSearchParams()
  const deepMarker = Number(params.get('marker')) || null

  const canvas = useRef<MapCanvasHandle>(null)
  const [filter, setFilter] = useState<Filter>('all')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [mode, setMode] = useState<AtlasMode>('view')
  const [managing, setManaging] = useState(false)
  /** Punto dell'immagine sotto il mirino, null se fuori: ricalcolato a ogni trasformazione. */
  const [center, setCenter] = useState<{ x: number; y: number } | null>(null)
  const [formPoint, setFormPoint] = useState<{ x: number; y: number } | null>(null)
  const [editing, setEditing] = useState<AtlasMarker | null>(null)
  const qc = useQueryClient()
  const toast = useToast()

  const { data: camp } = useQuery({ queryKey: ['campaign', campId], queryFn: () => api.campaigns.get(campId) })
  const isGm = !!camp?.is_gm
  const mapsQ = useQuery({ queryKey: ['atlas-maps', campId], queryFn: () => api.atlas.maps(campId) })
  const map = mapsQ.data?.find((m) => m.id === mId)
  const markersQ = useQuery({
    queryKey: ['atlas-markers', campId, mId],
    queryFn: () => api.atlas.markers(campId, mId),
    refetchInterval: (q) => (notFound(q.state.error) ? false : 15_000),
    retry: (n, e) => !notFound(e) && n < 3,
  })
  const unavailable = notFound(markersQ.error) || (mapsQ.isSuccess && !map)
  // Errore diverso da 404/403 (rete, 500): senza elenco mappe resterebbe lo skeleton per sempre.
  const failed = !unavailable && (mapsQ.isError || (markersQ.isError && !markersQ.data))

  const selected = markersQ.data?.find((m) => m.id === selectedId) ?? null
  const movingId = typeof mode === 'object' ? mode.move : null

  const readCenter = () => setCenter(canvas.current?.getCenterPoint() ?? null)
  useEffect(() => {
    if (mode === 'view') return
    // Spostando, il mirino parte dal marker; per un nuovo punto dal centro della vista attuale.
    const target = movingId != null ? markersQ.data?.find((m) => m.id === movingId) : null
    if (target) canvas.current?.centerOn({ x: target.x, y: target.y })
    readCenter()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode])

  const move = useMutation({
    mutationFn: (p: { x: number; y: number }) => api.atlas.updateMarker(campId, movingId!, p),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['atlas-markers', campId, mId] })
      setMode('view')
      setSelectedId(null)
    },
    onError: () => toast.error(t('common.action_failed')),
  })
  const place = () => {
    const p = canvas.current?.getCenterPoint()
    if (!p) return
    if (movingId != null) move.mutate(p)
    else { setFormPoint(p); setMode('view') }
  }
  const openLink = (target: number) =>
    navigate(`/campaign/${campId}/atlas/${target}`, { state: { trail: [...trail, { id: mId, name: map?.name ?? '' }], from: state.from } })

  const visible = useMemo(() => (markersQ.data ?? []).filter(FILTERS[filter]), [markersQ.data, filter])

  // Link dal feed (?marker=id): una volta caricati i marker, centra e seleziona.
  const deepDone = useRef(false)
  useEffect(() => {
    if (!deepMarker || deepDone.current || !markersQ.data) return
    const target = markersQ.data.find((m) => m.id === deepMarker)
    deepDone.current = true
    if (!target) return
    setSelectedId(target.id)
    canvas.current?.centerOn(target)
  }, [deepMarker, markersQ.data])

  const goBack = () => {
    if (trail.length > 0) navigate(-1)
    else navigate(state.from ?? `/campaign/${campId}`)
  }
  // Col mirino attivo il back di Telegram annulla il posizionamento invece di lasciare la pagina.
  usePageBack(mode !== 'view' ? () => setMode('view') : goBack)

  const backButton = (
    <Pressable
      onClick={goBack}
      aria-label={t('common.back')}
      className="shrink-0 w-11 h-11 flex items-center justify-center rounded-full bg-dnd-surface border border-dnd-gold-dim/30"
      whileTap={{ scale: 0.9 }}
    >
      <ChevronLeft size={22} className="text-dnd-gold-bright" />
    </Pressable>
  )

  if (unavailable || failed) {
    return (
      <div className="flex w-full flex-col items-center justify-center gap-4 bg-dnd-bg p-6 text-center" style={{ height: 'var(--tg-vh, 100vh)' }}>
        <p className="font-display text-lg font-bold text-dnd-gold-bright">{t(failed ? 'common.error' : 'atlas.unavailable')}</p>
        <p className="text-sm font-body text-dnd-text-muted">{t(failed ? 'common.action_failed' : 'atlas.unavailable_body')}</p>
        {failed && <Button onClick={() => { mapsQ.refetch(); markersQ.refetch() }}>{t('common.retry')}</Button>}
        <Button variant={failed ? 'secondary' : 'primary'} onClick={() => navigate(`/campaign/${campId}`)}>{t('atlas.back_to_campaign')}</Button>
      </div>
    )
  }

  return (
    <div
      className="flex w-full flex-col bg-dnd-bg"
      style={{ height: 'var(--tg-vh, 100vh)' }}
      data-mode={typeof mode === 'string' ? mode : 'move'}
    >
      <header className="z-10 shrink-0 space-y-2 border-b border-dnd-gold-dim/40 bg-dnd-surface-raised px-4 py-3 pt-safe shadow-parchment-md">
        <div className="flex items-center gap-3">
          {backButton}
          <div className="min-w-0 flex-1">
            <h1 className="truncate font-display text-lg font-bold text-dnd-gold-bright title-glow">{map?.name ?? t('atlas.title')}</h1>
            {trail.length > 0 && (
              <p className="truncate text-xs font-body text-dnd-text-muted">{trail.map((p) => p.name).join(' · ')}</p>
            )}
          </div>
          {isGm && map && (
            <Pressable
              onClick={() => setManaging(true)}
              aria-label={t('atlas.manage')}
              className="shrink-0 w-11 h-11 flex items-center justify-center rounded-full bg-dnd-surface border border-dnd-gold-dim/30"
            >
              <Settings2 size={20} className="text-dnd-gold-bright" />
            </Pressable>
          )}
        </div>
        <div className="-mx-1 flex gap-2 overflow-x-auto px-1 scrollbar-hide">
          {(['all', 'gm', 'group', 'mine'] as const)
            .filter((f) => !(isGm && f === 'mine'))
            .map((f) => (
              <FilterChip key={f} label={t(`atlas.filter_${f}`)} selected={filter === f} onToggle={() => setFilter(f)} className="shrink-0" />
            ))}
        </div>
      </header>

      <div className="relative min-h-0 flex-1">
        {map ? (
          <MapCanvas
            ref={canvas}
            src={api.atlas.mapImageUrl(campId, map.id, map.updated_at)}
            alt={map.name}
            markers={visible}
            selectedId={selectedId}
            isGm={isGm}
            onSelect={mode === 'view' ? setSelectedId : () => {}}
            onTransform={mode === 'view' ? undefined : readCenter}
            free={mode !== 'view'}
          />
        ) : (
          <Skeleton.Rect height="100%" />
        )}
        {map && mode === 'view' && (
          <Pressable
            onClick={() => setMode('place')}
            aria-label={t('atlas.new_marker')}
            className="absolute right-4 bottom-safe-fab z-30 flex h-14 w-14 items-center justify-center rounded-full bg-dnd-gold text-dnd-ink shadow-parchment-md"
          >
            <MapPinPlus size={24} />
          </Pressable>
        )}
        {map && mode !== 'view' && (
          <PlaceOverlay canPlace={center !== null} pending={move.isPending} onCancel={() => setMode('view')} onPlace={place} />
        )}
      </div>

      {selected && (
        <MarkerSheet
          open={mode === 'view' && !editing && !formPoint}
          campaignId={campId}
          marker={selected}
          isGm={isGm}
          linkName={mapsQ.data?.find((m) => m.id === selected.link_map_id)?.name ?? null}
          onClose={() => setSelectedId(null)}
          onOpenLink={openLink}
          onEdit={() => setEditing(selected)}
          onMove={() => setMode({ move: selected.id })}
        />
      )}
      {map && (
        <MarkerFormSheet
          open={!!formPoint || !!editing}
          campaignId={campId}
          mapId={mId}
          isGm={isGm}
          maps={mapsQ.data ?? []}
          point={formPoint}
          marker={editing}
          onClose={() => { setFormPoint(null); setEditing(null) }}
          onSaved={() => { setFormPoint(null); setEditing(null) }}
        />
      )}
      {isGm && map && <MapManageSheet open={managing} campaignId={campId} map={map} onClose={() => setManaging(false)} />}
    </div>
  )
}

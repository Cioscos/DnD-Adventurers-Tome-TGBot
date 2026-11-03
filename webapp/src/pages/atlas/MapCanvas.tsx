import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { TransformWrapper, TransformComponent, type ReactZoomPanPinchContentRef } from 'react-zoom-pan-pinch'
import { Minus, Plus } from 'lucide-react'
import Pressable from '@/components/ui/Pressable'
import MarkerPin from '@/pages/atlas/MarkerPin'
import { centerToImage, imageToCenter } from '@/lib/atlasCoords'
import type { AtlasMarker } from '@/types'

export interface MapCanvasHandle {
  /** Punto dell'immagine (0..1) sotto il centro della vista, null se il centro è fuori dall'immagine. */
  getCenterPoint(): { x: number; y: number } | null
  /** Porta il punto dell'immagine al centro della vista, ad almeno scala 2. */
  centerOn(p: { x: number; y: number }): void
}

interface Props {
  src: string
  alt: string
  markers: AtlasMarker[]
  selectedId: number | null
  isGm: boolean
  onSelect: (id: number) => void
  onTransform?: (scale: number) => void
  /** Pan libero oltre i bordi (mirino): con i limiti il centro non raggiunge mai il bordo dell'immagine. */
  free?: boolean
}

type Size = { width: number; height: number }

/** Mappa a schermo intero con pan/zoom; i marker sono figli assoluti dell'immagine adattata (contain). */
const MapCanvas = forwardRef<MapCanvasHandle, Props>(function MapCanvas(
  { src, alt, markers, selectedId, isGm, onSelect, onTransform, free = false }, ref,
) {
  const { t } = useTranslation()
  const zoom = useRef<ReactZoomPanPinchContentRef>(null)
  const box = useRef<HTMLDivElement>(null)
  const [view, setView] = useState<Size>({ width: 0, height: 0 })
  const [natural, setNatural] = useState<Size | null>(null)
  const [scale, setScale] = useState(1)
  const raf = useRef(0)
  const pendingCenter = useRef<{ x: number; y: number } | null>(null)

  useEffect(() => {
    const el = box.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(([e]) => setView({ width: e.contentRect.width, height: e.contentRect.height }))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  useEffect(() => () => cancelAnimationFrame(raf.current), [])

  // Immagine adattata alla vista (contain): sono le dimensioni del div su cui poggiano i marker.
  const k = natural && view.width ? Math.min(view.width / natural.width, view.height / natural.height) : 0
  const fit = k ? { width: natural!.width * k, height: natural!.height * k } : null

  const doCenter = (p: { x: number; y: number }) => {
    const z = zoom.current
    if (!z || !fit) { pendingCenter.current = p; return }
    const s = Math.max(z.instance.transformState.scale, 2)
    const pos = imageToCenter(p, view, fit, s)
    z.setTransform(pos.positionX, pos.positionY, s, 300)
  }
  useImperativeHandle(ref, () => ({
    getCenterPoint: () => {
      const z = zoom.current
      return z && fit ? centerToImage(z.instance.transformState, view, fit) : null
    },
    centerOn: doCenter,
  }))
  // Deep link arrivato prima che l'immagine fosse caricata e misurata.
  useEffect(() => {
    if (fit && pendingCenter.current) {
      const p = pendingCenter.current
      pendingCenter.current = null
      doCenter(p)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fit?.width, fit?.height])
  // Uscendo dal mirino la mappa torna dentro i limiti (bounds già ricalcolati dall'update del wrapper).
  // Solo sulla transizione free → false: al mount un'animazione qui rovinerebbe il centerOnInit.
  const wasFree = useRef(free)
  useEffect(() => {
    const z = zoom.current
    const b = z?.instance.bounds
    const leaving = wasFree.current && !free
    wasFree.current = free
    if (!leaving || !z || !b) return
    const { positionX, positionY, scale: s } = z.instance.transformState
    const x = Math.min(Math.max(positionX, b.minPositionX), b.maxPositionX)
    const y = Math.min(Math.max(positionY, b.minPositionY), b.maxPositionY)
    if (x !== positionX || y !== positionY) z.setTransform(x, y, s, 300)
  }, [free])

  return (
    <div ref={box} className="relative h-full w-full overflow-hidden">
      <TransformWrapper
        ref={zoom}
        minScale={1}
        maxScale={8}
        centerOnInit
        limitToBounds={!free}
        doubleClick={{ disabled: true }}
        onTransformed={(_, st) => {
          // Al massimo un aggiornamento per frame: il pinch emette molti eventi.
          cancelAnimationFrame(raf.current)
          raf.current = requestAnimationFrame(() => { setScale(st.scale); onTransform?.(st.scale) })
        }}
      >
        {/* Niente flex-centering: la libreria centra già il contenuto (vedi ZoomableImage). */}
        <TransformComponent wrapperClass="!w-full !h-full">
          <div className="relative" style={fit ?? { width: 0, height: 0 }}>
            <img
              src={src}
              alt={alt}
              draggable={false}
              decoding="async"
              className="block h-full w-full select-none object-contain"
              onLoad={(e) => setNatural({ width: e.currentTarget.naturalWidth, height: e.currentTarget.naturalHeight })}
            />
            {markers.map((mk) => (
              <MarkerPin key={mk.id} marker={mk} scale={scale} isGm={isGm} selected={mk.id === selectedId} onSelect={onSelect} />
            ))}
          </div>
        </TransformComponent>
      </TransformWrapper>
      <div className="absolute left-4 bottom-safe-fab z-30 flex flex-col gap-2">
        {([['zoom_in', Plus, () => zoom.current?.zoomIn()], ['zoom_out', Minus, () => zoom.current?.zoomOut()]] as const).map(([key, Icon, fn]) => (
          <Pressable
            key={key}
            onClick={fn}
            aria-label={t(`atlas.${key}`)}
            className="flex h-11 w-11 items-center justify-center rounded-full border border-dnd-gold-dim/40 bg-dnd-surface-raised shadow-parchment-md"
          >
            <Icon size={20} className="text-dnd-gold-bright" />
          </Pressable>
        ))}
      </div>
    </div>
  )
})

export default MapCanvas

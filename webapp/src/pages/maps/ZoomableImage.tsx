import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch'

interface ZoomableImageProps {
  src: string
  alt: string
}

/** Lazy-loaded pinch-zoom wrapper for fullscreen map overlay. */
export default function ZoomableImage({ src, alt }: ZoomableImageProps) {
  return (
    <TransformWrapper
      initialScale={1}
      minScale={0.5}
      maxScale={6}
      centerOnInit
      doubleClick={{ mode: 'reset' }}
      wheel={{ step: 0.2 }}
      pinch={{ step: 8 }}
      panning={{ velocityDisabled: false }}
    >
      {/* Niente flex-centering qui: la libreria centra già il contenuto via
          translate; sommare il centering flex raddoppia l'offset (immagine
          spinta in basso a destra). */}
      <TransformComponent wrapperClass="!w-full !h-full">
        <img
          src={src}
          alt={alt}
          className="max-w-full max-h-[calc(100vh-7rem)] rounded-xl object-contain shadow-parchment-2xl select-none"
          draggable={false}
        />
      </TransformComponent>
    </TransformWrapper>
  )
}

import { useTranslation } from 'react-i18next'
import Button from '@/components/ui/Button'

interface Props {
  /** false quando il centro della vista è fuori dall'immagine. */
  canPlace: boolean
  pending: boolean
  onCancel: () => void
  onPlace: () => void
}

/** Mirino fisso al centro: l'utente trascina la mappa sotto. Tutto pointer-events-none
 *  tranne la barra, così il pan funziona anche toccando sopra il mirino. */
export default function PlaceOverlay({ canPlace, pending, onCancel, onPlace }: Props) {
  const { t } = useTranslation()
  return (
    <div className="pointer-events-none absolute inset-0 z-30" data-place-overlay>
      <p className="absolute left-1/2 top-3 w-max max-w-[calc(100%-2rem)] -translate-x-1/2 rounded-lg border border-dnd-border bg-dnd-surface-raised/95 px-3 py-1.5 text-center text-xs font-body text-dnd-text shadow-parchment-md">
        {t('atlas.place_hint')}
      </p>
      {/* Il centro esatto del mirino è il punto (x, y) che verrà salvato. */}
      <div className="absolute left-1/2 top-1/2 h-12 w-12 -translate-x-1/2 -translate-y-1/2 text-dnd-gold-bright drop-shadow-[0_0_2px_rgba(13,10,8,0.9)]" aria-hidden>
        <span className="absolute left-1/2 top-0 h-full w-0.5 -translate-x-1/2 bg-current" />
        <span className="absolute left-0 top-1/2 h-0.5 w-full -translate-y-1/2 bg-current" />
        <span className="absolute left-1/2 top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-current" />
      </div>
      {/* A destra della colonna zoom (left-4 + 44px), alla stessa altezza. */}
      <div className="pointer-events-auto absolute bottom-safe-fab left-[4.5rem] right-4 space-y-2">
        {!canPlace && (
          <p className="rounded-lg border border-dnd-border bg-dnd-surface-raised/95 px-3 py-1.5 text-center text-xs font-body text-dnd-text-muted">
            {t('atlas.off_map')}
          </p>
        )}
        <div className="flex gap-2">
          <Button variant="secondary" fullWidth onClick={onCancel}>{t('common.cancel')}</Button>
          <Button fullWidth disabled={!canPlace} loading={pending} onClick={onPlace}>{t('atlas.place_here')}</Button>
        </div>
      </div>
    </div>
  )
}

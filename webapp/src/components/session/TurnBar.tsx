import { useTranslation } from 'react-i18next'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import Surface from '@/components/ui/Surface'

interface Props {
  round: number
  activeName: string | null
  amGm: boolean
  pending: boolean
  onPrev: () => void
  onNext: () => void
}

export default function TurnBar({ round, activeName, amGm, pending, onPrev, onNext }: Props) {
  const { t } = useTranslation()
  return (
    <Surface variant="elevated">
      <div className="flex items-center justify-between gap-2">
        {amGm ? (
          <button
            type="button"
            onClick={onPrev}
            disabled={pending}
            aria-label={t('session.combat.prev')}
            className="w-11 h-11 inline-flex items-center justify-center rounded-full
                       bg-dnd-chip-bg border border-dnd-gold-dim/40 text-dnd-gold-bright
                       active:scale-95 disabled:opacity-40"
          >
            <ChevronLeft size={20} />
          </button>
        ) : <div className="w-11" />}
        <div className="text-center min-w-0">
          <p className="text-xs uppercase tracking-widest text-dnd-gold-dim font-cinzel">
            {t('session.combat.round_label', { n: round })}
          </p>
          {activeName && (
            <p className="font-display font-bold text-dnd-gold-bright break-words">
              {t('session.combat.turn_of', { name: activeName })}
            </p>
          )}
        </div>
        {amGm ? (
          <button
            type="button"
            onClick={onNext}
            disabled={pending}
            aria-label={t('session.combat.next')}
            className="w-11 h-11 inline-flex items-center justify-center rounded-full
                       bg-dnd-chip-bg border border-dnd-gold-dim/40 text-dnd-gold-bright
                       active:scale-95 disabled:opacity-40"
          >
            <ChevronRight size={20} />
          </button>
        ) : <div className="w-11" />}
      </div>
    </Surface>
  )
}

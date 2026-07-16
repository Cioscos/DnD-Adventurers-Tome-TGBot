import { m } from 'framer-motion'
import Pressable from '@/components/ui/Pressable'
import type { CharacterScreen } from '@/store/characterStore'

interface Props {
  active: CharacterScreen
  onSelect: (idx: CharacterScreen) => void
  labels: [string, string, string]
}

export default function SwiperDots({ active, onSelect, labels }: Props) {
  return (
    <div
      role="tablist"
      aria-label="Character screens"
      className="absolute bottom-safe left-0 right-0 z-30 flex justify-center pointer-events-none"
    >
      {/* Il pallino è il segnale visivo; il bottone attorno è l'area di tocco
          (≥40px), invisibile, così i tre tab restano usabili col pollice. */}
      {[0, 1, 2].map((idx) => {
        const isActive = idx === active
        return (
          <Pressable
            key={idx}
            type="button"
            role="tab"
            aria-selected={isActive}
            aria-label={labels[idx]}
            onClick={() => onSelect(idx as CharacterScreen)}
            className="min-w-[40px] min-h-[40px] flex items-center justify-center pointer-events-auto"
            whileTap={{ scale: 0.9 }}
          >
            <m.span
              className={`block rounded-full border border-dnd-gold-dim/40 ${
                isActive ? 'bg-dnd-gold-bright' : 'bg-dnd-gold/30'
              }`}
              animate={{ width: isActive ? 24 : 8 }}
              initial={false}
              style={{ height: 8 }}
              transition={{ duration: 0.2 }}
            />
          </Pressable>
        )
      })}
    </div>
  )
}

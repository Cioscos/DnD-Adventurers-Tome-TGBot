import { m } from 'framer-motion'
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
      className="absolute bottom-2 left-0 right-0 z-30 flex justify-center gap-2 pointer-events-auto"
    >
      {[0, 1, 2].map((idx) => {
        const isActive = idx === active
        return (
          <m.button
            key={idx}
            type="button"
            role="tab"
            aria-selected={isActive}
            aria-label={labels[idx]}
            onClick={() => onSelect(idx as CharacterScreen)}
            className="rounded-full border border-dnd-gold-dim/40"
            style={{
              width: isActive ? 24 : 8,
              height: 8,
              background: isActive
                ? 'var(--dnd-gold-bright, #d4af37)'
                : 'rgba(212,175,55,0.3)',
            }}
            transition={{ duration: 0.2 }}
            whileTap={{ scale: 0.9 }}
          />
        )
      })}
    </div>
  )
}

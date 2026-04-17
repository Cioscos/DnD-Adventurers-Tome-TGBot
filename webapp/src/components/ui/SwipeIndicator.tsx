import { m, AnimatePresence } from 'framer-motion'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface SwipeIndicatorProps {
  direction: 'left' | 'right' | null
  progress?: number
}

/**
 * Edge chevron indicator shown while user is swiping horizontally.
 * progress 0..1 drives opacity.
 */
export default function SwipeIndicator({ direction, progress = 0 }: SwipeIndicatorProps) {
  const opacity = Math.min(1, Math.max(0, progress))

  return (
    <AnimatePresence>
      {direction && (
        <m.div
          className={`fixed top-1/2 -translate-y-1/2 z-30 pointer-events-none
                      ${direction === 'left' ? 'left-2' : 'right-2'}`}
          initial={{ opacity: 0, scale: 0.7 }}
          animate={{ opacity, scale: 1 }}
          exit={{ opacity: 0, scale: 0.7 }}
        >
          <div className="w-10 h-10 rounded-full bg-dnd-gold/20 border border-dnd-gold flex items-center justify-center shadow-halo-gold">
            {direction === 'left'
              ? <ChevronLeft className="text-dnd-gold" size={20} />
              : <ChevronRight className="text-dnd-gold" size={20} />}
          </div>
        </m.div>
      )}
    </AnimatePresence>
  )
}

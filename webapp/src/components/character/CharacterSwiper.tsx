import { useEffect, useRef, useState, type ReactNode } from 'react'
import { m, useMotionValue, animate, useReducedMotion } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { useCharacterStore, type CharacterScreen } from '@/store/characterStore'
import SwiperDots from './SwiperDots'

interface Props {
  hero: ReactNode
  equipment: ReactNode
  menu: ReactNode
}

const VELOCITY_THRESHOLD = 500
const OFFSET_RATIO = 0.2

export default function CharacterSwiper({ hero, equipment, menu }: Props) {
  const { t } = useTranslation()
  const activeScreen = useCharacterStore((s) => s.activeScreen)
  const setActiveScreen = useCharacterStore((s) => s.setActiveScreen)
  const reduced = useReducedMotion()

  const containerRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  const x = useMotionValue(0)

  // Track viewport width
  useEffect(() => {
    if (!containerRef.current) return
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 0
      setWidth(w)
    })
    ro.observe(containerRef.current)
    return () => ro.disconnect()
  }, [])

  // Sync x to active screen whenever activeScreen or width changes.
  useEffect(() => {
    if (width === 0) return
    const target = -activeScreen * width
    if (reduced) {
      x.set(target)
    } else {
      animate(x, target, { type: 'spring', stiffness: 320, damping: 32 })
    }
  }, [activeScreen, width, x, reduced])

  const handleDragEnd = (
    _e: unknown,
    info: { offset: { x: number }; velocity: { x: number } },
  ) => {
    const offset = info.offset.x
    const velocity = info.velocity.x
    let next: CharacterScreen = activeScreen
    if (velocity < -VELOCITY_THRESHOLD || offset < -width * OFFSET_RATIO) {
      next = Math.min(2, activeScreen + 1) as CharacterScreen
    } else if (velocity > VELOCITY_THRESHOLD || offset > width * OFFSET_RATIO) {
      next = Math.max(0, activeScreen - 1) as CharacterScreen
    }
    setActiveScreen(next)
  }

  const labels: [string, string, string] = [
    t('character.swiper.screen.hero', { defaultValue: 'Character' }),
    t('character.swiper.screen.equipment', { defaultValue: 'Equipment' }),
    t('character.swiper.screen.menu', { defaultValue: 'Menu' }),
  ]

  return (
    <div ref={containerRef} className="relative flex-1 overflow-hidden touch-pan-y">
      <m.div
        className="flex h-full"
        style={{ x, width: width * 3 }}
        drag="x"
        dragConstraints={{ left: -2 * width, right: 0 }}
        dragElastic={0.2}
        dragMomentum={false}
        onDragEnd={handleDragEnd}
      >
        <div style={{ width }} className="h-full overflow-y-auto">{hero}</div>
        <div style={{ width }} className="h-full overflow-y-auto">{equipment}</div>
        <div style={{ width }} className="h-full overflow-y-auto">{menu}</div>
      </m.div>
      <SwiperDots active={activeScreen} onSelect={setActiveScreen} labels={labels} />
    </div>
  )
}

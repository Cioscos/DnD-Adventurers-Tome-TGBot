import { useEffect, useRef, useState, type ReactNode } from 'react'
import { m, useMotionValue, animate, useReducedMotion, type PanInfo } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { useCharacterStore, type CharacterScreen } from '@/store/characterStore'
import SwiperDots from './SwiperDots'

interface Props {
  hero: ReactNode
  equipment: ReactNode
  menu: ReactNode
}

const VELOCITY_THRESHOLD = 500
const OFFSET_RATIO = 0.25

export default function CharacterSwiper({ hero, equipment, menu }: Props) {
  const { t } = useTranslation()
  const activeScreen = useCharacterStore((s) => s.activeScreen)
  const setActiveScreen = useCharacterStore((s) => s.setActiveScreen)
  const reduced = useReducedMotion()

  const containerRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  const x = useMotionValue(0)

  // Track container width via ResizeObserver
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 0
      if (w > 0) setWidth(w)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Snap to current screen whenever activeScreen or width changes
  useEffect(() => {
    if (width === 0) return
    const target = -activeScreen * width
    if (Math.abs(x.get() - target) < 1) return
    if (reduced) {
      x.set(target)
    } else {
      const controls = animate(x, target, {
        type: 'spring',
        stiffness: 360,
        damping: 32,
      })
      return () => controls.stop()
    }
  }, [activeScreen, width, x, reduced])

  const handleDragEnd = (_e: unknown, info: PanInfo) => {
    const offset = info.offset.x
    const velocity = info.velocity.x
    let next: CharacterScreen = activeScreen
    if (velocity < -VELOCITY_THRESHOLD || offset < -width * OFFSET_RATIO) {
      next = Math.min(2, activeScreen + 1) as CharacterScreen
    } else if (velocity > VELOCITY_THRESHOLD || offset > width * OFFSET_RATIO) {
      next = Math.max(0, activeScreen - 1) as CharacterScreen
    }
    if (next !== activeScreen) {
      setActiveScreen(next)
    } else {
      // No screen change — animate back to current screen offset
      const target = -activeScreen * width
      if (reduced) {
        x.set(target)
      } else {
        animate(x, target, { type: 'spring', stiffness: 360, damping: 32 })
      }
    }
  }

  const labels: [string, string, string] = [
    t('character.swiper.screen.hero', { defaultValue: 'Character' }),
    t('character.swiper.screen.equipment', { defaultValue: 'Equipment' }),
    t('character.swiper.screen.menu', { defaultValue: 'Menu' }),
  ]

  return (
    <div ref={containerRef} className="relative flex-1 min-h-0 overflow-hidden">
      <m.div
        className="flex h-full will-change-transform"
        style={{ x, width: width * 3, touchAction: 'pan-y' }}
        drag={width > 0 ? 'x' : false}
        dragConstraints={{ left: -2 * width, right: 0 }}
        dragElastic={0.15}
        dragDirectionLock
        onDragEnd={handleDragEnd}
      >
        <div style={{ width, touchAction: 'pan-y' }} className="h-full overflow-y-auto shrink-0">{hero}</div>
        <div style={{ width, touchAction: 'pan-y' }} className="h-full overflow-y-auto shrink-0">{equipment}</div>
        <div style={{ width, touchAction: 'pan-y' }} className="h-full overflow-y-auto shrink-0">{menu}</div>
      </m.div>
      <SwiperDots active={activeScreen} onSelect={setActiveScreen} labels={labels} />
    </div>
  )
}

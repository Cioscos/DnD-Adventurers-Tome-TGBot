import { useEffect, useRef, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useCharacterStore, type CharacterScreen } from '@/store/characterStore'
import SwiperDots from './SwiperDots'

interface Props {
  hero: ReactNode
  equipment: ReactNode
  menu: ReactNode
}

export default function CharacterSwiper({ hero, equipment, menu }: Props) {
  const { t } = useTranslation()
  const activeScreen = useCharacterStore((s) => s.activeScreen)
  const setActiveScreen = useCharacterStore((s) => s.setActiveScreen)

  const trackRef = useRef<HTMLDivElement>(null)
  const panelRefs = useRef<Array<HTMLDivElement | null>>([null, null, null])

  // Programmatic scroll when activeScreen changes (e.g. dot tap, character switch).
  useEffect(() => {
    const track = trackRef.current
    const target = panelRefs.current[activeScreen]
    if (!track || !target) return
    // Avoid feedback loop if we're already at the right offset.
    if (Math.abs(track.scrollLeft - target.offsetLeft) < 4) return
    track.scrollTo({ left: target.offsetLeft, behavior: 'smooth' })
  }, [activeScreen])

  // Sync activeScreen from native scroll (drag/swipe).
  useEffect(() => {
    const track = trackRef.current
    if (!track) return
    let raf: number | null = null
    const onScroll = () => {
      if (raf !== null) return
      raf = requestAnimationFrame(() => {
        raf = null
        const w = track.clientWidth
        if (w === 0) return
        const idx = Math.round(track.scrollLeft / w)
        const clamped = Math.max(0, Math.min(2, idx)) as CharacterScreen
        if (clamped !== activeScreen) {
          setActiveScreen(clamped)
        }
      })
    }
    track.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      track.removeEventListener('scroll', onScroll)
      if (raf !== null) cancelAnimationFrame(raf)
    }
  }, [activeScreen, setActiveScreen])

  const labels: [string, string, string] = [
    t('character.swiper.screen.hero', { defaultValue: 'Character' }),
    t('character.swiper.screen.equipment', { defaultValue: 'Equipment' }),
    t('character.swiper.screen.menu', { defaultValue: 'Menu' }),
  ]

  const setPanelRef = (idx: number) => (el: HTMLDivElement | null) => {
    panelRefs.current[idx] = el
  }

  return (
    <div className="relative flex-1 min-h-0 flex">
      <div
        ref={trackRef}
        className="flex-1 flex overflow-x-auto overflow-y-hidden snap-x snap-mandatory scroll-smooth scrollbar-hide"
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
      >
        <div ref={setPanelRef(0)} className="snap-center shrink-0 w-full h-full overflow-y-auto">{hero}</div>
        <div ref={setPanelRef(1)} className="snap-center shrink-0 w-full h-full overflow-y-auto">{equipment}</div>
        <div ref={setPanelRef(2)} className="snap-center shrink-0 w-full h-full overflow-y-auto">{menu}</div>
      </div>
      <SwiperDots active={activeScreen} onSelect={setActiveScreen} labels={labels} />
    </div>
  )
}

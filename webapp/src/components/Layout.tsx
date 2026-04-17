import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ChevronLeft } from 'lucide-react'
import { m } from 'framer-motion'
import { useSwipeNavigation, getGroupInfo } from '@/hooks/useSwipeNavigation'
import { spring } from '@/styles/motion'

interface LayoutProps {
  title: string
  children: React.ReactNode
  backTo?: string
  group?: string
  page?: string
}

export default function Layout({ title, children, backTo, group, page }: LayoutProps) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const swipe = useSwipeNavigation(group, page)
  const info = getGroupInfo(group, page)

  const handleBack = () => {
    if (backTo) navigate(backTo)
    else navigate(-1)
  }

  return (
    <div className="min-h-screen w-full flex flex-col bg-dnd-bg">
      <m.header
        className="sticky top-0 z-10 flex flex-col px-4 py-3 pt-safe
                    bg-dnd-surface-raised/95 backdrop-blur-sm
                    border-b border-dnd-gold-dim/40 shadow-parchment-md"
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={spring.drift}
      >
        <div className="flex items-center gap-3">
          <m.button
            onClick={handleBack}
            className="w-9 h-9 flex items-center justify-center rounded-full bg-dnd-surface border border-dnd-gold-dim/30"
            aria-label="Indietro"
            whileTap={{ scale: 0.9 }}
            whileHover={{ boxShadow: 'var(--halo-gold)' }}
          >
            <ChevronLeft size={20} className="text-dnd-gold-bright" />
          </m.button>
          <h1 className="text-lg font-bold font-display text-dnd-gold-bright truncate flex-1"
              style={{ textShadow: '0 1px 4px var(--dnd-gold-glow)' }}>
            {title}
          </h1>
        </div>
        {info && (() => {
          const prevKey = info.index > 0 ? info.pages[info.index - 1] : null
          const currKey = info.pages[info.index]
          const nextKey = info.index < info.total - 1 ? info.pages[info.index + 1] : null
          return (
            <div className="flex items-center justify-center gap-1.5 mt-2 text-xs overflow-x-auto scrollbar-hide font-body">
              {prevKey && (
                <>
                  <span className="text-dnd-text-muted opacity-70 whitespace-nowrap"
                        style={{ filter: 'blur(0.5px)' }}>
                    {t(`character.menu.${prevKey}`)}
                  </span>
                  <span className="text-dnd-gold-dim/50 shrink-0">◈</span>
                </>
              )}
              <span className="text-dnd-gold-bright font-semibold whitespace-nowrap">
                {t(`character.menu.${currKey}`)}
              </span>
              {nextKey && (
                <>
                  <span className="text-dnd-gold-dim/50 shrink-0">◈</span>
                  <span className="text-dnd-text-muted opacity-70 whitespace-nowrap"
                        style={{ filter: 'blur(0.5px)' }}>
                    {t(`character.menu.${nextKey}`)}
                  </span>
                </>
              )}
            </div>
          )
        })()}
      </m.header>

      <main
        ref={swipe.contentRef}
        className="flex-1 min-w-0 p-4 space-y-3 pb-safe animate-fade-in"
        onTouchStart={swipe.onTouchStart}
        onTouchMove={swipe.onTouchMove}
        onTouchEnd={swipe.onTouchEnd}
      >
        {children}
      </main>
    </div>
  )
}

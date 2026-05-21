import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ChevronLeft } from 'lucide-react'
import { m } from 'framer-motion'
import { useSwipeNavigation, getGroupInfo } from '@/hooks/useSwipeNavigation'
import { spring } from '@/styles/motion'
import { haptic } from '@/auth/telegram'

interface LayoutProps {
  title: string
  children: React.ReactNode
  /** @deprecated Kept for compatibility — Layout always uses history.back() now. */
  backTo?: string
  group?: string
  page?: string
  /** Hide native scrollbar on the scrolling main region. */
  hideScrollbar?: boolean
}

export default function Layout({ title, children, group, page, hideScrollbar = false }: LayoutProps) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const swipe = useSwipeNavigation(group, page)
  const info = getGroupInfo(group, page)
  const { id } = useParams<{ id: string }>()

  const handleBack = () => {
    navigate(-1)
  }

  return (
    <div
      className="w-full flex flex-col bg-dnd-bg"
      style={{ height: 'var(--tg-vh, 100vh)' }}
    >
      <m.header
        className="shrink-0 z-10 flex flex-col px-4 py-3 pt-safe
                    bg-dnd-surface-raised/95 backdrop-blur-sm
                    border-b border-dnd-gold-dim/40 shadow-parchment-md"
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={spring.drift}
      >
        <div className="flex items-center gap-3">
          <m.button
            onClick={handleBack}
            className="shrink-0 w-11 h-11 flex items-center justify-center rounded-full bg-dnd-surface border border-dnd-gold-dim/30"
            aria-label="Indietro"
            whileTap={{ scale: 0.9 }}
            whileHover={{ boxShadow: 'var(--halo-gold)' }}
          >
            <ChevronLeft size={22} className="text-dnd-gold-bright" />
          </m.button>
          <h1 className="text-lg font-bold font-display text-dnd-gold-bright truncate flex-1 title-glow">
            {title}
          </h1>
        </div>
        {info && (() => {
          const prevKey = info.index > 0 ? info.pages[info.index - 1] : null
          const currKey = info.pages[info.index]
          const nextKey = info.index < info.total - 1 ? info.pages[info.index + 1] : null

          const goToPrev = () => {
            if (prevKey && id) {
              haptic.light()
              navigate(`/char/${id}/${prevKey}`, { replace: true })
            }
          }
          const goToNext = () => {
            if (nextKey && id) {
              haptic.light()
              navigate(`/char/${id}/${nextKey}`, { replace: true })
            }
          }

          return (
            <div className="flex items-center justify-center gap-1.5 mt-2 text-xs overflow-x-auto scrollbar-hide font-body">
              {prevKey && (
                <>
                  <m.button
                    type="button"
                    onClick={goToPrev}
                    whileTap={{ scale: 0.95 }}
                    aria-label={t('layout.nav.go_to', { page: t(`character.menu.${prevKey}`) })}
                    className="text-dnd-text-muted opacity-70 whitespace-nowrap px-2 py-1.5 min-h-[32px] rounded hover:filter-none hover:text-dnd-gold-bright hover:opacity-100 transition-colors"
                    style={{ filter: 'blur(0.5px)' }}
                  >
                    {t(`character.menu.${prevKey}`)}
                  </m.button>
                  <span className="text-dnd-gold-dim/50 shrink-0">◈</span>
                </>
              )}
              <span className="text-dnd-gold-bright font-semibold whitespace-nowrap">
                {t(`character.menu.${currKey}`)}
              </span>
              {nextKey && (
                <>
                  <span className="text-dnd-gold-dim/50 shrink-0">◈</span>
                  <m.button
                    type="button"
                    onClick={goToNext}
                    whileTap={{ scale: 0.95 }}
                    aria-label={t('layout.nav.go_to', { page: t(`character.menu.${nextKey}`) })}
                    className="text-dnd-text-muted opacity-70 whitespace-nowrap px-2 py-1.5 min-h-[32px] rounded hover:filter-none hover:text-dnd-gold-bright hover:opacity-100 transition-colors"
                    style={{ filter: 'blur(0.5px)' }}
                  >
                    {t(`character.menu.${nextKey}`)}
                  </m.button>
                </>
              )}
            </div>
          )
        })()}
      </m.header>

      <main
        ref={swipe.contentRef}
        className={`flex-1 min-w-0 overflow-y-auto p-4 pt-4 pb-[max(env(safe-area-inset-bottom),5.5rem)] space-y-3 animate-fade-in${hideScrollbar ? ' scrollbar-hide' : ''}`}
        onTouchStart={swipe.onTouchStart}
        onTouchMove={swipe.onTouchMove}
        onTouchEnd={swipe.onTouchEnd}
      >
        {children}
      </main>
    </div>
  )
}

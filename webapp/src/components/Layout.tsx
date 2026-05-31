import { useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ChevronLeft } from 'lucide-react'
import { m, AnimatePresence } from 'framer-motion'
import { useSwipeNavigation, getGroupInfo } from '@/hooks/useSwipeNavigation'
import { pageSkeleton } from '@/components/skeletons/pageSkeletons'
import { spring } from '@/styles/motion'
import { haptic } from '@/auth/telegram'

interface LayoutProps {
  title: string
  children: React.ReactNode
  /** Logical parent route to return to (typically the character hub `/char/:id`).
   * When set, the back arrow navigates there directly instead of walking the
   * browser history one step at a time. Falls back to history.back() if absent. */
  backTo?: string
  group?: string
  page?: string
  /** Hide native scrollbar on the scrolling main region. */
  hideScrollbar?: boolean
}

export default function Layout({ title, children, backTo, group, page, hideScrollbar = false }: LayoutProps) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const swipe = useSwipeNavigation(group, page)
  const info = getGroupInfo(group, page)
  const { id } = useParams<{ id: string }>()

  // Ghost skeleton: the skeleton of the page the swipe is heading toward, so the
  // area behind the outgoing page is never blank during the drag.
  const ghostKey = info && swipe.ghostDir !== 0
    ? info.pages[info.index + swipe.ghostDir]
    : undefined
  const GhostSkeleton = pageSkeleton(ghostKey)

  // Tablist collapse: hide the breadcrumb row once the user scrolls past a small
  // threshold; show it again once they scroll back up. Keeps mobile real estate
  // free when the on-screen keyboard or long content is in play.
  const [tablistCollapsed, setTablistCollapsed] = useState(false)
  const lastScrollTopRef = useRef(0)

  // Finding #5: prefer the declared logical parent (e.g. the character hub) over
  // history.back(), so a single tap from a deep page returns to /char/:id instead
  // of unwinding the navigation stack one cross-link at a time.
  const handleBack = () => {
    if (backTo) navigate(backTo)
    else navigate(-1)
  }

  const handleMainScroll = (e: React.UIEvent<HTMLElement>) => {
    const top = e.currentTarget.scrollTop
    const prev = lastScrollTopRef.current
    const delta = top - prev
    lastScrollTopRef.current = top
    if (top < 16) {
      if (tablistCollapsed) setTablistCollapsed(false)
      return
    }
    if (delta > 6 && !tablistCollapsed) setTablistCollapsed(true)
    else if (delta < -6 && tablistCollapsed) setTablistCollapsed(false)
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
            <AnimatePresence initial={false}>
              {!tablistCollapsed && (
                <m.div
                  key="breadcrumb"
                  initial={{ height: 0, opacity: 0, marginTop: 0 }}
                  animate={{ height: 'auto', opacity: 1, marginTop: 8 }}
                  exit={{ height: 0, opacity: 0, marginTop: 0 }}
                  transition={{ duration: 0.18, ease: [0.25, 0.1, 0.25, 1] }}
                  className="overflow-hidden"
                >
                  <div className="flex items-center justify-center gap-1.5 text-xs overflow-x-auto scrollbar-hide font-body">
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
                </m.div>
              )}
            </AnimatePresence>
          )
        })()}
      </m.header>

      <div className="relative flex-1 min-w-0 overflow-hidden">
        <main
          ref={swipe.contentRef}
          className={`absolute inset-0 overflow-y-auto p-4 pt-4 pb-[max(env(safe-area-inset-bottom),6rem)] space-y-3 animate-fade-in${hideScrollbar ? ' scrollbar-hide' : ''}`}
          onTouchStart={swipe.onTouchStart}
          onTouchMove={swipe.onTouchMove}
          onTouchEnd={swipe.onTouchEnd}
          onScroll={handleMainScroll}
        >
          {children}
        </main>

        {/* Ghost layer: skeleton of the incoming page, only while swiping. */}
        {info && swipe.ghostDir !== 0 && (
          <div
            ref={swipe.ghostRef}
            aria-hidden
            className="absolute inset-0 overflow-hidden p-4 pt-4 pointer-events-none"
          >
            <GhostSkeleton />
          </div>
        )}
      </div>
    </div>
  )
}

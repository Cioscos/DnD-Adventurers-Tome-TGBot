import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { ChevronLeft, RefreshCw, UserX } from 'lucide-react'
import { m, AnimatePresence } from 'framer-motion'
import { useSwipeNavigation, getGroupInfo } from '@/hooks/useSwipeNavigation'
import { pageSkeleton } from '@/components/skeletons/pageSkeletons'
import { api, ApiError } from '@/api/client'
import EmptyState from '@/components/ui/EmptyState'
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

  // Guard condiviso sul personaggio (audit FE 2026-06-11, #10): con un id
  // inesistente (deep-link stantio, personaggio eliminato altrove) le pagine
  // restavano su skeleton/main vuoto perché nessuna gestiva isError. La query
  // è la stessa delle pagine (stessa key → dedupe), quindi non costa fetch
  // extra; qui si decide solo cosa mostrare al posto del contenuto.
  // SOLO sulle route /char/:id — altre route con un param :id (es. /session/:id)
  // non devono interpretarlo come personaggio: a un giocatore la stanza
  // sessione veniva oscurata da un finto "personaggio non trovato" (403).
  const { pathname } = useLocation()
  const isCharRoute = pathname.startsWith('/char/')
  const charId = Number(id)
  const charQuery = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId),
    enabled: isCharRoute && Number.isFinite(charId) && charId > 0,
    retry: (failureCount, error) =>
      !(error instanceof ApiError && (error.status === 404 || error.status === 403)) && failureCount < 3,
  })
  const charNotFound = isCharRoute && charQuery.error instanceof ApiError
    && (charQuery.error.status === 404 || charQuery.error.status === 403)

  // Ghost skeleton: the skeleton of the page the swipe is heading toward, so the
  // area behind the outgoing page is never blank during the drag.
  const ghostKey = info && swipe.ghostDir !== 0
    ? info.pages[info.index + swipe.ghostDir]
    : undefined
  const GhostSkeleton = pageSkeleton(ghostKey)

  // Tablist collapse: hide the breadcrumb row when the user scrolls down, reveal
  // it when they scroll back up. Keeps mobile real estate free when the on-screen
  // keyboard or long content is in play.
  //
  // Stability matters here: collapsing shrinks the header, which grows <main> and
  // fires more scroll events — a naive per-event delta toggle oscillates, making
  // the breadcrumb animation flicker ("vibrate"). We harden it with (1) one
  // update per animation frame, (2) accumulated directional travel instead of
  // per-event delta, and (3) a short lock after each toggle so the resize-induced
  // scroll events can't flip the state back.
  const [tablistCollapsed, setTablistCollapsed] = useState(false)
  const lastScrollTopRef = useRef(0)
  const accumRef = useRef(0)        // accumulated travel in the current direction
  const rafPendingRef = useRef(false)
  const lockUntilRef = useRef(0)    // ignore toggles until this timestamp (ms)

  // Breadcrumb auto-scroll: when the current page changes, scroll the strip so
  // the highlighted item is centered in the scrollable container.
  const crumbScrollRef = useRef<HTMLDivElement>(null)
  const activeCrumbRef = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    const c = crumbScrollRef.current
    const a = activeCrumbRef.current
    if (!c || !a) return
    const cRect = c.getBoundingClientRect()
    const aRect = a.getBoundingClientRect()
    const delta = (aRect.left - cRect.left) - (c.clientWidth - a.offsetWidth) / 2
    c.scrollBy({ left: delta, behavior: 'smooth' })
  }, [page, group])

  // Finding #5: prefer the declared logical parent (e.g. the character hub) over
  // history.back(), so a single tap from a deep page returns to /char/:id instead
  // of unwinding the navigation stack one cross-link at a time.
  const handleBack = () => {
    if (backTo) navigate(backTo)
    else navigate(-1)
  }

  const handleMainScroll = (e: React.UIEvent<HTMLElement>) => {
    // Capture scrollTop now: e.currentTarget is no longer valid inside the rAF.
    const top = e.currentTarget.scrollTop
    if (rafPendingRef.current) return
    rafPendingRef.current = true
    requestAnimationFrame(() => {
      rafPendingRef.current = false
      const delta = top - lastScrollTopRef.current
      lastScrollTopRef.current = top

      // Near the top: always reveal, and reset the accumulator.
      if (top < 16) {
        accumRef.current = 0
        setTablistCollapsed((c) => (c ? false : c))
        return
      }
      // Respect the post-toggle lock so the header-resize scroll burst can't
      // flip the state back (the source of the flicker).
      if (Date.now() < lockUntilRef.current) return

      // Accumulate directional travel; reset when direction flips.
      if (Math.sign(delta) !== Math.sign(accumRef.current)) accumRef.current = 0
      accumRef.current += delta

      const TRAVEL = 24 // px of continuous travel before toggling
      if (accumRef.current > TRAVEL) {
        accumRef.current = 0
        setTablistCollapsed((c) => {
          if (!c) lockUntilRef.current = Date.now() + 220
          return true
        })
      } else if (accumRef.current < -TRAVEL) {
        accumRef.current = 0
        setTablistCollapsed((c) => {
          if (c) lockUntilRef.current = Date.now() + 220
          return false
        })
      }
    })
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
          const goToPage = (pageKey: string) => {
            if (id) {
              haptic.light()
              navigate(`/char/${id}/${pageKey}`, { replace: true })
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
                  <div ref={crumbScrollRef} className="flex items-center overflow-x-auto scrollbar-hide touch-pan-x text-xs font-body whitespace-nowrap px-1">
                    {info.pages.map((pageKey, i) => (
                      <span key={pageKey} className="flex items-center shrink-0">
                        {i > 0 && (
                          <span className="text-dnd-gold-dim/50 shrink-0 px-1">◈</span>
                        )}
                        {i === info.index ? (
                          <span ref={activeCrumbRef} className="text-dnd-gold-bright font-semibold whitespace-nowrap px-2 py-1.5">
                            {t(`character.menu.${pageKey}`)}
                          </span>
                        ) : (
                          <m.button
                            type="button"
                            onClick={() => goToPage(pageKey)}
                            whileTap={{ scale: 0.95 }}
                            aria-label={t('layout.nav.go_to', { page: t(`character.menu.${pageKey}`) })}
                            className="text-dnd-text-muted opacity-70 whitespace-nowrap px-2 py-1.5 min-h-[32px] rounded hover:filter-none hover:text-dnd-gold-bright hover:opacity-100 transition-colors"
                            style={{ filter: 'blur(0.5px)' }}
                          >
                            {t(`character.menu.${pageKey}`)}
                          </m.button>
                        )}
                      </span>
                    ))}
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
          className={`absolute inset-0 overflow-y-auto overflow-x-hidden overscroll-contain p-4 pt-4 pb-[max(env(safe-area-inset-bottom),var(--tg-content-bottom,0px),6rem)] space-y-3 animate-fade-in${hideScrollbar ? ' scrollbar-hide' : ''}`}
          onTouchStart={swipe.onTouchStart}
          onTouchMove={swipe.onTouchMove}
          onTouchEnd={swipe.onTouchEnd}
          onScroll={handleMainScroll}
        >
          {isCharRoute && charQuery.isError ? (
            charNotFound ? (
              <EmptyState
                icon={<UserX size={28} />}
                title={t('layout.char_error.not_found')}
                hint={t('layout.char_error.not_found_hint')}
                action={{
                  label: t('layout.char_error.back_to_list'),
                  onClick: () => navigate('/'),
                }}
              />
            ) : (
              <EmptyState
                icon={<RefreshCw size={28} />}
                title={t('layout.char_error.generic')}
                action={{
                  label: t('layout.char_error.retry'),
                  onClick: () => charQuery.refetch(),
                }}
              />
            )
          ) : (
            children
          )}
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

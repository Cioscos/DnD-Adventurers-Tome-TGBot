import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { ChevronLeft, RefreshCw, UserX } from 'lucide-react'
import { m } from 'framer-motion'
import { useSwipeNavigation, getGroupInfo } from '@/hooks/useSwipeNavigation'
import { usePageBack } from '@/hooks/useOverlayDismiss'
import { pageSkeleton } from '@/components/skeletons/pageSkeletons'
import { api, ApiError } from '@/api/client'
import EmptyState from '@/components/ui/EmptyState'
import ServerVersionBanner from '@/components/ui/ServerVersionBanner'
import OfflineNotice, { type OfflineNoticeQuery } from '@/components/ui/OfflineNotice'
import Pressable from '@/components/ui/Pressable'
import PendingSavesBanner from '@/components/PendingSavesBanner'
import PageHelp from '@/components/PageHelp'
import { spring } from '@/styles/motion'

// Ogni pagina monta il proprio Layout, quindi navigare fra pagine dello stesso
// gruppo (swipe, breadcrumb) ricrea l'header. Questi valori gli danno continuità:
// resta fermo invece di rifare l'ingresso e la striscia non riparte da sinistra.
let mountedGroup: string | undefined
let crumbScrollLeft = 0
let crumbCollapsed = false

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
  /** Query dei dati mostrati dalla pagina, quando non sono quelli del personaggio:
   * è di questa che l'avviso offline deve riportare lo stato e l'orario. */
  offlineQuery?: OfflineNoticeQuery
  /** Chiave della guida "?" (`help.<key>` nei locale). Default: `page`. */
  help?: string
}

// Altezza della fascia breadcrumb: riga tappabile da 44 px + pb-3 + bordo.
// shortcut: costante, non misurata — se cambia l'altezza della riga va aggiornata qui.
const CRUMB_STRIP_PX = 57

export default function Layout({ title, children, backTo, group, page, hideScrollbar = false, offlineQuery, help = page }: LayoutProps) {
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
    ? swipe.slideTarget ?? info.pages[info.index + swipe.ghostDir]
    : undefined
  // Il breadcrumb toccato si accende subito, senza aspettare la fine della slide.
  const activeKey = swipe.slideTarget ?? page
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
  // Calcolato al primo render, mentre il Layout uscente è ancora montato.
  const [sameGroup] = useState(() => !!group && mountedGroup === group)
  useEffect(() => {
    mountedGroup = group
    return () => {
      mountedGroup = undefined
    }
  }, [group])
  // La pagina nuova parte dall'alto, quindi i breadcrumb vanno riaperti: se erano
  // chiusi si parte da chiusi e si riaprono animati, senza far saltare il contenuto.
  const [tablistCollapsed, setTablistCollapsed] = useState(() => sameGroup && crumbCollapsed)
  useEffect(() => {
    setTablistCollapsed(false)
  }, [])
  useEffect(() => {
    crumbCollapsed = tablistCollapsed
  }, [tablistCollapsed])
  const crumbsOpen = !!info && !tablistCollapsed
  // Arrivo da swipe: lo skeleton con cui la pagina è entrata sfuma nel contenuto.
  const [arrivalVisible, setArrivalVisible] = useState(!!swipe.arrivedBySwipe)
  const ArrivalSkeleton = pageSkeleton(page)
  const lastScrollTopRef = useRef(0)
  const accumRef = useRef(0)        // accumulated travel in the current direction
  const rafPendingRef = useRef(false)
  const lockUntilRef = useRef(0)    // ignore toggles until this timestamp (ms)

  // Breadcrumb auto-scroll: when the current page changes, scroll the strip so
  // the highlighted item is centered in the scrollable container.
  const crumbScrollRef = useRef<HTMLDivElement>(null)
  const activeCrumbRef = useRef<HTMLSpanElement>(null)

  useLayoutEffect(() => {
    const c = crumbScrollRef.current
    const a = activeCrumbRef.current
    if (!c || !a) return
    if (sameGroup) c.scrollLeft = crumbScrollLeft
    const cRect = c.getBoundingClientRect()
    const aRect = a.getBoundingClientRect()
    const delta = (aRect.left - cRect.left) - (c.clientWidth - a.offsetWidth) / 2
    c.scrollBy({ left: delta, behavior: 'smooth' })
    // sameGroup è fisso per tutta la vita del componente.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeKey, group])

  // Finding #5: prefer the declared logical parent (e.g. the character hub) over
  // history.back(), so a single tap from a deep page returns to /char/:id instead
  // of unwinding the navigation stack one cross-link at a time.
  const handleBack = () => {
    if (backTo) navigate(backTo)
    else navigate(-1)
  }
  // Stessa destinazione per il back hardware/BackButton di Telegram (Android).
  usePageBack(handleBack)

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
        className={`shrink-0 z-10 flex flex-col px-4 py-3 pt-safe
                    bg-dnd-surface-raised border-b
                    ${crumbsOpen ? 'border-transparent' : 'border-dnd-gold-dim/40 shadow-parchment-md'}`}
        initial={sameGroup ? false : { y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={spring.drift}
      >
        <div className="flex items-center gap-3">
          <Pressable
            onClick={handleBack}
            className="shrink-0 w-11 h-11 flex items-center justify-center rounded-full bg-dnd-surface border border-dnd-gold-dim/30"
            aria-label={t('common.back')}
            whileTap={{ scale: 0.9 }}
            whileHover={{ boxShadow: 'var(--halo-gold)' }}
          >
            <ChevronLeft size={22} className="text-dnd-gold-bright" />
          </Pressable>
          <h1 className="text-lg font-bold font-display text-dnd-gold-bright truncate flex-1 title-glow">
            {title}
          </h1>
          {help && <PageHelp helpKey={help} title={title} />}
        </div>
      </m.header>

      <ServerVersionBanner />
      {isCharRoute && charId > 0 && <PendingSavesBanner charId={charId} />}

      <div className="relative isolate flex-1 min-w-0 overflow-hidden">
        {/* Breadcrumb: fascia sovrapposta sotto l'header che scorre via con un transform.
            Animarne l'altezza dentro l'header ricalcolava tutta la pagina a ogni frame
            di scroll (S22: picchi da ~100 ms). Lo spazio sotto è riservato da uno spacer
            in <main>; gli sticky delle pagine si spostano sotto la fascia con --crumb-offset. */}
        {info && (
          <m.div
            className="absolute inset-x-0 top-0 z-30 px-4 pb-3 bg-dnd-surface-raised border-b border-dnd-gold-dim/40 shadow-parchment-md"
            initial={false}
            animate={crumbsOpen ? { y: 0, opacity: 1 } : { y: '-100%', opacity: 0 }}
            transition={{ duration: 0.18, ease: [0.25, 0.1, 0.25, 1] }}
            style={{ pointerEvents: crumbsOpen ? 'auto' : 'none' }}
          >
          <div
            ref={crumbScrollRef}
            onScroll={(e) => { crumbScrollLeft = e.currentTarget.scrollLeft }}
            className="flex items-center overflow-x-auto scrollbar-hide touch-pan-x text-xs font-body whitespace-nowrap px-1"
          >
            {info.pages.map((pageKey, i) => (
              <span key={pageKey} className="flex items-center shrink-0">
                {i > 0 && (
                  <span className="text-dnd-gold-dim/50 shrink-0 px-1">◈</span>
                )}
                {pageKey === activeKey ? (
                  <span ref={activeCrumbRef} className="inline-flex items-center min-h-[44px] text-dnd-gold-bright font-semibold whitespace-nowrap px-2 py-1.5">
                    {t(`character.menu.${pageKey}`)}
                  </span>
                ) : (
                  <Pressable
                    type="button"
                    onClick={() => swipe.goToPage(pageKey)}
                    whileTap={{ scale: 0.95 }}
                    aria-label={t('layout.nav.go_to', { page: t(`character.menu.${pageKey}`) })}
                    className="text-dnd-gold-dim whitespace-nowrap px-2 py-1.5 min-h-[44px] min-w-[44px] rounded hover:text-dnd-gold-bright transition-colors"
                  >
                    {t(`character.menu.${pageKey}`)}
                  </Pressable>
                )}
              </span>
            ))}
          </div>
          </m.div>
        )}
        <main
          ref={swipe.contentRef}
          className={`absolute inset-0 overflow-y-auto overflow-x-hidden overscroll-contain p-4 pt-4 pb-safe-fab space-y-3${info ? ' touch-pan-y' : ''}${swipe.arrivedBySwipe ? '' : ' animate-fade-in'}${hideScrollbar ? ' scrollbar-hide' : ''}`}
          onTouchStart={swipe.onTouchStart}
          onTouchMove={swipe.onTouchMove}
          onTouchEnd={swipe.onTouchEnd}
          onTouchCancel={swipe.onTouchEnd}
          onScroll={handleMainScroll}
          style={info ? ({ '--crumb-offset': crumbsOpen ? `${CRUMB_STRIP_PX}px` : '0px' } as React.CSSProperties) : undefined}
        >
          {/* Riserva l'altezza della fascia breadcrumb (meno il gap di space-y-3 che segue). */}
          {info && <div aria-hidden style={{ height: CRUMB_STRIP_PX - 12 }} />}
          {/* Prima il 404/403, che sconfessa anche una copia in cache; poi l'errore
              senza dati. Con dati in cache la pagina resta, segnalata dall'avviso. */}
          {charNotFound ? (
            <EmptyState
              icon={<UserX size={28} />}
              title={t('layout.char_error.not_found')}
              hint={t('layout.char_error.not_found_hint')}
              action={{
                label: t('layout.char_error.back_to_list'),
                onClick: () => navigate('/'),
              }}
            />
          ) : isCharRoute && charQuery.isError && charQuery.data === undefined ? (
            <EmptyState
              icon={<RefreshCw size={28} />}
              title={t('layout.char_error.generic')}
              action={{
                label: t('layout.char_error.retry'),
                onClick: () => charQuery.refetch(),
              }}
            />
          ) : (
            <>
              <OfflineNotice query={offlineQuery ?? charQuery} />
              {children}
            </>
          )}
        </main>

        {/* touch-pan-y su <main>: l'orizzontale è dello swipe di pagina, non del
            browser (che farebbe il suo back o annullerebbe il tocco a metà gesto). */}
        {/* Ghost layer: skeleton of the incoming page, only while swiping. */}
        {info && swipe.ghostDir !== 0 && (
          <div
            ref={swipe.ghostRef}
            aria-hidden
            className="absolute inset-0 overflow-hidden p-4 pt-4 pointer-events-none"
            // Già fuori schermo dal primo frame, prima del primo touchmove che lo muove.
            style={{ transform: `translateX(${swipe.ghostDir === -1 ? '-100%' : '100%'})` }}
          >
            <GhostSkeleton />
          </div>
        )}

        {arrivalVisible && (
          <m.div
            aria-hidden
            className="absolute inset-0 overflow-hidden p-4 pt-4 pointer-events-none bg-dnd-bg"
            initial={{ opacity: 1 }}
            animate={{ opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            onAnimationComplete={() => setArrivalVisible(false)}
          >
            <ArrivalSkeleton />
          </m.div>
        )}
      </div>
    </div>
  )
}

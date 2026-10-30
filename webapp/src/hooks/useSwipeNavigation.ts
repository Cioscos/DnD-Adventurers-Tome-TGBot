import { useRef, useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useModal } from '@/components/modalContext'
import { haptic } from '@/auth/telegram'
import { isAnyOverlayOpen } from '@/hooks/useOverlayDismiss'
import { useReducedMotion } from '@/hooks/useReducedMotion'

// Il gesto parte da qui dentro? Allora non è uno swipe di pagina: righe di chip
// a scroll orizzontale, campi di testo (selezione/cursore), opt-out espliciti.
const NO_PAGE_SWIPE = '[data-no-page-swipe], .overflow-x-auto, .overflow-x-scroll, input, textarea, [contenteditable="true"]'

// Quando un gesto cambia pagina: oltre metà schermo, oppure con un flick deciso.
// Un trascinamento lento e corto torna indietro.
const COMMIT_RATIO = 0.5
const FLICK_VELOCITY = 0.45 // px/ms
const FLICK_MIN_DISTANCE = 30 // px

const SLIDE_MIN_MS = 120
const SLIDE_MAX_MS = 280
const SLIDE_MIN_SPEED = 1.4 // px/ms: un rilascio lento non trascina la slide
const RETURN_MS = 220
const SLIDE_EASE = 'cubic-bezier(0.22, 1, 0.36, 1)'

// Vero fra la fine della slide e il mount della pagina di arrivo (ogni pagina ha
// il proprio Layout, quindi il segnale passa da un'istanza del hook alla successiva).
let slideArrival = false

const PAGE_GROUPS: Record<string, string[]> = {
  combat: ['hp', 'ac', 'saves', 'actions'],
  magic: ['spells', 'slots'],
  skills: ['stats', 'skills', 'abilities'],
  equipment: ['inventory', 'currency'],
  character: ['identity', 'class', 'xp', 'conditions'],
  tools: ['dice', 'notes', 'maps', 'history'],
}

export function getGroupInfo(group?: string, page?: string) {
  if (!group || !page) return null
  const pages = PAGE_GROUPS[group]
  if (!pages) return null
  const index = pages.indexOf(page)
  if (index === -1) return null
  return { pages, index, total: pages.length }
}

export function useSwipeNavigation(group?: string, page?: string) {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const { isModalOpen } = useModal()
  const reducedMotion = useReducedMotion()
  const touchRef = useRef({
    startX: 0, startY: 0, swiping: false, locked: false,
    dragX: 0, translate: 0, dir: 0, lastX: 0, lastT: 0, velocity: 0,
  })
  const contentRef = useRef<HTMLDivElement>(null)
  const ghostRef = useRef<HTMLDivElement>(null)
  const [ghostDir, setGhostDir] = useState<-1 | 0 | 1>(0)
  // Pagina scelta da un breadcrumb, anche non adiacente, durante la sua slide.
  const [slideTarget, setSlideTarget] = useState<string | null>(null)
  // Animazione di rilascio in corso: i tocchi vengono ignorati finché non finisce.
  const settleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Arrivo da uno swipe: Layout fa sfumare lo skeleton invece del fade-in di pagina.
  const [arrivedBySwipe] = useState(() => slideArrival)

  useEffect(() => {
    slideArrival = false
    return () => {
      if (settleTimerRef.current) clearTimeout(settleTimerRef.current)
    }
  }, [])

  const info = getGroupInfo(group, page)

  const onTouchStart = useCallback((e: React.TouchEvent) => {
    if (isModalOpen || !info || settleTimerRef.current) return
    const touch = e.touches[0]
    // Gli eventi React risalgono anche dai portal: un drag dentro uno Sheet
    // aperto (figlio di Layout nell'albero) navigava alla pagina accanto.
    const target = e.target as Element | null
    const blocked = isAnyOverlayOpen() || !!target?.closest?.(NO_PAGE_SWIPE)
    touchRef.current = {
      startX: touch.clientX, startY: touch.clientY, swiping: false, locked: blocked,
      dragX: 0, translate: 0, dir: 0, lastX: touch.clientX, lastT: performance.now(), velocity: 0,
    }
  }, [isModalOpen, info])

  const onTouchMove = useCallback((e: React.TouchEvent) => {
    if (isModalOpen || !info || settleTimerRef.current) return
    const touch = e.touches[0]
    const t = touchRef.current
    const deltaX = touch.clientX - t.startX
    const deltaY = touch.clientY - t.startY

    // Once a gesture is recognized as vertical scroll, lock OUT horizontal swipe
    // for the rest of this touch so a mid-scroll horizontal drift can't hijack it.
    if (t.locked) return

    // Only engage if horizontal intent clearly dominates.
    if (!t.swiping) {
      const ax = Math.abs(deltaX)
      const ay = Math.abs(deltaY)
      if (ay > ax && ay > 8) {
        // Vertical intent → lock and let the list scroll.
        t.locked = true
        return
      }
      if (ax > ay * 2 && ax > 16) {
        t.swiping = true
      } else {
        return
      }
    }

    // Velocità del dito (px/ms), smussata: decide il flick al rilascio.
    const now = performance.now()
    const dt = now - t.lastT
    if (dt > 0) {
      t.velocity = 0.7 * ((touch.clientX - t.lastX) / dt) + 0.3 * t.velocity
      t.lastX = touch.clientX
      t.lastT = now
    }

    if (contentRef.current) {
      const atEdge = (deltaX > 0 && info.index === 0) || (deltaX < 0 && info.index === info.total - 1)
      const translate = atEdge ? deltaX * 0.3 : deltaX
      t.dragX = deltaX
      t.translate = translate
      contentRef.current.style.transform = `translateX(${translate}px)`
      contentRef.current.style.transition = 'none'

      // Ghost direction: dragging right (deltaX>0) reveals the PREVIOUS page on
      // the left; dragging left reveals the NEXT page on the right. None at edge.
      const dir: -1 | 0 | 1 = atEdge ? 0 : deltaX > 0 ? -1 : 1
      t.dir = dir
      if (dir !== ghostDir) setGhostDir(dir)

      if (ghostRef.current && dir !== 0) {
        // Ghost sits just off-screen on the incoming side and slides in with the finger.
        const base = dir === -1 ? '-100%' : '100%'
        ghostRef.current.style.transform = `translateX(calc(${base} + ${translate}px))`
        ghostRef.current.style.transition = 'none'
      }
    }
  }, [isModalOpen, info, ghostDir])

  const onTouchEnd = useCallback(() => {
    if (settleTimerRef.current) return
    const t = touchRef.current
    if (!info || !t.swiping) {
      t.swiping = false
      t.locked = false
      setGhostDir(0)
      return
    }
    t.swiping = false
    t.locked = false

    const content = contentRef.current
    const ghost = ghostRef.current
    const width = content?.offsetWidth ?? 0
    // Dito rimasto fermo prima di alzarsi: la velocità registrata è vecchia.
    const velocity = performance.now() - t.lastT > 80 ? 0 : t.velocity
    const distance = Math.abs(t.dragX)
    const flicked = Math.abs(velocity) >= FLICK_VELOCITY
      && distance >= FLICK_MIN_DISTANCE
      && Math.sign(velocity) === Math.sign(t.dragX)
    const target = info.pages[info.index + (t.dragX > 0 ? -1 : 1)]
    const commit = !!target && t.dir !== 0 && (distance >= width * COMMIT_RATIO || flicked)

    if (commit && reducedMotion) {
      haptic.light()
      navigate(`/char/${id}/${target}`, { replace: true })
      return
    }

    if (commit) {
      // La pagina esce dal lato verso cui andava il dito e la nuova la segue,
      // alla velocità del gesto; si naviga a slide finita, a schermo già pieno.
      haptic.light()
      const remaining = Math.max(0, width - Math.abs(t.translate))
      const ms = Math.round(Math.min(SLIDE_MAX_MS, Math.max(SLIDE_MIN_MS, remaining / Math.max(Math.abs(velocity), SLIDE_MIN_SPEED))))
      const easing = `transform ${ms}ms ${SLIDE_EASE}`
      if (content) {
        content.style.transition = easing
        content.style.transform = `translateX(${t.dragX > 0 ? '100%' : '-100%'})`
      }
      if (ghost) {
        ghost.style.transition = easing
        ghost.style.transform = 'translateX(0)'
      }
      settleTimerRef.current = setTimeout(() => {
        settleTimerRef.current = null
        slideArrival = true
        navigate(`/char/${id}/${target}`, { replace: true })
      }, ms)
      return
    }

    // Gesto non concluso: torna al punto di partenza, con il ghost al suo fianco.
    const easing = `transform ${RETURN_MS}ms ${SLIDE_EASE}`
    if (content) {
      content.style.transition = easing
      content.style.transform = 'translateX(0)'
    }
    if (ghost) {
      ghost.style.transition = easing
      ghost.style.transform = `translateX(${t.dir === -1 ? '-100%' : '100%'})`
    }
    settleTimerRef.current = setTimeout(() => {
      settleTimerRef.current = null
      if (contentRef.current) {
        contentRef.current.style.transition = ''
        contentRef.current.style.transform = ''
      }
      setGhostDir(0)
    }, RETURN_MS)
  }, [info, navigate, id, reducedMotion])

  // Tocco su un breadcrumb: stessa slide dello swipe, nel verso della pagina scelta.
  const goToPage = useCallback((pageKey: string) => {
    if (!info || settleTimerRef.current) return
    const targetIndex = info.pages.indexOf(pageKey)
    if (targetIndex === -1 || targetIndex === info.index) return
    haptic.light()
    const path = `/char/${id}/${pageKey}`
    if (reducedMotion) {
      navigate(path, { replace: true })
      return
    }
    const dir = targetIndex > info.index ? 1 : -1
    setSlideTarget(pageKey)
    setGhostDir(dir)
    settleTimerRef.current = setTimeout(() => {
      settleTimerRef.current = null
      slideArrival = true
      navigate(path, { replace: true })
    }, SLIDE_MAX_MS)
    // Il ghost nasce fuori schermo col render di questo tocco: la slide parte dal
    // frame dopo, a posizione iniziale già applicata (o non ci sarebbe transizione).
    requestAnimationFrame(() => {
      const content = contentRef.current
      const ghost = ghostRef.current
      const easing = `transform ${SLIDE_MAX_MS}ms ${SLIDE_EASE}`
      ghost?.getBoundingClientRect()
      if (content) {
        content.style.transition = easing
        content.style.transform = `translateX(${dir === 1 ? '-100%' : '100%'})`
      }
      if (ghost) {
        ghost.style.transition = easing
        ghost.style.transform = 'translateX(0)'
      }
    })
  }, [info, id, navigate, reducedMotion])

  return {
    contentRef,
    ghostRef,
    ghostDir,
    slideTarget,
    goToPage,
    arrivedBySwipe,
    onTouchStart,
    onTouchMove,
    onTouchEnd,
    currentIndex: info?.index ?? 0,
    total: info?.total ?? 1,
  }
}

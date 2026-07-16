import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, matchPath } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { GiPerspectiveDiceSixFacesRandom as Dices } from 'react-icons/gi'
import DiceIcon from '@/components/ui/DiceIcon'
import Pressable from '@/components/ui/Pressable'
import DicePoolResultModal from '@/components/DicePoolResultModal'
import { useCharacterStore } from '@/store/characterStore'
import { useAnyOverlayOpen } from '@/store/overlayStore'
import { haptic } from '@/auth/telegram'
import { api } from '@/api/client'
import { useRollAndPersist, type RollEntry, type RollGroup } from '@/dice/useRollAndPersist'
import type { DiceKind } from '@/dice/types'

const KINDS: DiceKind[] = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20', 'd100']
const SIDES_FOR = {
  d4: 4, d6: 6, d8: 8, d10: 10, d12: 12, d20: 20, d100: 100,
} as const satisfies Record<DiceKind, number>
const ERROR_DISMISS_MS = 3000
const POOL_CAP = 100

type DicePool = Partial<Record<DiceKind, number>>

function useOverlayVisibility(): { visible: boolean; charId: number | null } {
  const location = useLocation()
  const activeCharId = useCharacterStore((s) => s.activeCharId)

  return useMemo(() => {
    const path = location.pathname
    if (matchPath('/char/:id/dice', path)) return { visible: false, charId: null }
    if (matchPath('/char/:id/settings', path)) return { visible: false, charId: null }

    const charAny = matchPath('/char/:id/*', path) ?? matchPath('/char/:id', path)
    if (charAny) {
      const id = Number(charAny.params.id)
      return { visible: Number.isFinite(id), charId: Number.isFinite(id) ? id : null }
    }

    if (matchPath('/session/:id', path) && activeCharId != null) {
      return { visible: true, charId: activeCharId }
    }

    return { visible: false, charId: null }
  }, [location.pathname, activeCharId])
}

export default function DiceOverlay() {
  const { t } = useTranslation()
  const { visible, charId } = useOverlayVisibility()
  // Hide the launcher whenever a modal/sheet/dialog is open so it never floats
  // above the backdrop and steals taps from modal buttons (finding #3).
  const anyOverlayOpen = useAnyOverlayOpen()
  const [open, setOpen] = useState(false)
  const [pool, setPool] = useState<DicePool>({})
  // Dim the launcher while the page is actively scrolling so it stops covering
  // content the user is reading; it stays tappable and fades back when idle.
  const [scrolling, setScrolling] = useState(false)

  const [results, setResults] = useState<RollGroup[] | null>(null)
  const [warningText, setWarningText] = useState<string | null>(null)

  const dismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const longPressFiredRef = useRef(false)

  const { data: char } = useQuery({
    queryKey: ['character', charId],
    queryFn: () => api.characters.get(charId!),
    enabled: charId != null,
  })

  useEffect(() => {
    return () => {
      if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current)
      if (longPressTimerRef.current) clearTimeout(longPressTimerRef.current)
    }
  }, [])

  // Capture-phase listener catches scroll on any descendant scroll container
  // (Layout's <main>, the character swiper screens, ...) since scroll doesn't
  // bubble. Debounced so the launcher fades back ~600ms after scrolling stops.
  useEffect(() => {
    let idleTimer: ReturnType<typeof setTimeout> | null = null
    const onScroll = () => {
      setScrolling(true)
      if (idleTimer) clearTimeout(idleTimer)
      idleTimer = setTimeout(() => setScrolling(false), 600)
    }
    window.addEventListener('scroll', onScroll, true)
    return () => {
      window.removeEventListener('scroll', onScroll, true)
      if (idleTimer) clearTimeout(idleTimer)
    }
  }, [])

  const showWarning = useCallback((text: string) => {
    setWarningText(text)
    if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current)
    dismissTimerRef.current = setTimeout(() => setWarningText(null), ERROR_DISMISS_MS)
  }, [])

  const { roll, isPending } = useRollAndPersist(charId)

  const entries = useMemo(
    () => (Object.entries(pool) as Array<[DiceKind, number]>).filter(([, n]) => n > 0),
    [pool]
  )
  const poolTotal = entries.reduce((s, [, n]) => s + n, 0)
  const isRolling = isPending

  const handleRoll = useCallback(async () => {
    if (!entries.length || isPending || !charId) return
    try {
      const rollEntries: RollEntry[] = entries.map(([kind, count]) => ({ kind, count }))
      const groups = await roll(rollEntries, {
        notation: rollEntries.map((e) => `${e.count}${e.kind}`).join(' + '),
      })
      setPool({})
      setOpen(false)
      haptic.medium()
      setResults(groups)
    } catch {
      haptic.error()
      showWarning(t('character.dice_overlay.roll_failed'))
    }
  }, [entries, isPending, charId, roll, showWarning, t])

  const increment = useCallback((kind: DiceKind) => {
    setPool((p) => {
      const total = Object.values(p).reduce((s, n) => s + (n ?? 0), 0)
      if (total >= POOL_CAP) {
        haptic.warning()
        showWarning(t('character.dice_overlay.pool_cap_reached'))
        return p
      }
      haptic.light()
      return { ...p, [kind]: (p[kind] ?? 0) + 1 }
    })
  }, [showWarning, t])

  const clearKind = useCallback((kind: DiceKind) => {
    haptic.medium()
    setPool((p) => {
      const { [kind]: _removed, ...rest } = p
      return rest
    })
  }, [])

  const handlePointerDown = useCallback((kind: DiceKind) => {
    longPressFiredRef.current = false
    longPressTimerRef.current = setTimeout(() => {
      longPressFiredRef.current = true
      clearKind(kind)
    }, 500)
  }, [clearKind])

  const handlePointerUpOrLeave = useCallback(() => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current)
      longPressTimerRef.current = null
    }
  }, [])

  const handleKindClick = useCallback((kind: DiceKind) => {
    if (longPressFiredRef.current) {
      longPressFiredRef.current = false
      return
    }
    increment(kind)
  }, [increment])

  const toggleOpen = useCallback(() => {
    haptic.light()
    setOpen((o) => !o)
    setPool({})
  }, [])

  if (!visible) return null

  return (
    <>
      {!anyOverlayOpen && (
      <div className="fixed bottom-4 right-4 z-40">
        <AnimatePresence>
          {open && (
            <m.div
              className="absolute bottom-full right-0 mb-2 flex flex-col-reverse gap-1.5"
              initial={{ opacity: 0, scaleY: 0.6, transformOrigin: 'bottom' }}
              animate={{ opacity: 1, scaleY: 1 }}
              exit={{ opacity: 0, scaleY: 0.6 }}
              transition={{ type: 'spring', stiffness: 320, damping: 26 }}
            >
              {KINDS.map((kind, idx) => {
                const count = pool[kind] ?? 0
                return (
                  <Pressable
                    key={kind}
                    onClick={() => handleKindClick(kind)}
                    onPointerDown={() => handlePointerDown(kind)}
                    onPointerUp={handlePointerUpOrLeave}
                    onPointerLeave={handlePointerUpOrLeave}
                    onPointerCancel={handlePointerUpOrLeave}
                    disabled={isRolling}
                    className="relative w-12 h-12 rounded-2xl bg-dnd-surface-raised border border-dnd-border
                               flex items-center justify-center text-dnd-gold-bright select-none
                               touch-manipulation [-webkit-touch-callout:none]
                               hover:border-dnd-gold/60 hover:shadow-halo-gold transition-[box-shadow,border-color]
                               disabled:opacity-40"
                    whileTap={{ scale: 0.9 }}
                    initial={{ opacity: 0, x: 10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: idx * 0.03 }}
                    aria-label={kind}
                  >
                    <DiceIcon sides={SIDES_FOR[kind]} size={28} />
                    {count > 0 && (
                      <span className="absolute -top-1 -right-1 min-w-[20px] h-5 px-1
                                       rounded-full bg-dnd-crimson text-dnd-parchment text-[11px]
                                       font-bold font-mono flex items-center justify-center
                                       border border-dnd-surface-raised">
                        {count}
                      </span>
                    )}
                  </Pressable>
                )
              })}
            </m.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {poolTotal > 0 && (
            <Pressable
              onClick={handleRoll}
              pending={isRolling}
              spinnerSize={16}
              className="absolute right-full top-0 mr-2 h-14 px-5 rounded-2xl
                         bg-gradient-gold
                         border border-dnd-gold-dim shadow-halo-gold
                         flex items-center justify-center gap-2 text-dnd-ink
                         font-cinzel uppercase tracking-wider font-bold text-sm
                         disabled:opacity-60 whitespace-nowrap"
              initial={{ opacity: 0, x: 10, scale: 0.9 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 10, scale: 0.9 }}
              whileTap={{ scale: 0.95 }}
              transition={{ type: 'spring', stiffness: 320, damping: 24 }}
            >
              <Dices size={18} />
              {isRolling ? t('character.dice_overlay.rolling') : t('character.dice_overlay.roll')}
            </Pressable>
          )}
        </AnimatePresence>

        <Pressable
          aria-label={open ? t('character.dice_overlay.close') : t('character.dice_overlay.open')}
          onClick={toggleOpen}
          className="w-14 h-14 rounded-full
                     bg-gradient-gold
                     border border-dnd-gold-dim shadow-halo-gold
                     flex items-center justify-center text-dnd-ink touch-manipulation"
          whileTap={{ scale: 0.9 }}
          initial={{ opacity: 0, scale: 0.6 }}
          animate={{ opacity: scrolling && !open ? 0.35 : 1, scale: 1, rotate: open ? 45 : 0 }}
          transition={{ type: 'spring', stiffness: 260, damping: 22 }}
        >
          <Dices size={26} />
        </Pressable>
      </div>
      )}

      {results && results.length > 0 && charId != null && (
        <DicePoolResultModal
          charId={charId}
          initialResults={results}
          inspirationAvailable={Boolean(char?.heroic_inspiration)}
          onClose={() => setResults(null)}
        />
      )}

      <AnimatePresence>
        {warningText && (
          <Pressable
            role="alert"
            onClick={() => setWarningText(null)}
            className="fixed bottom-24 left-4 right-4 mx-auto z-[55]
                       max-w-xs
                       rounded-2xl bg-dnd-surface-raised/95 backdrop-blur-md
                       border border-dnd-crimson shadow-parchment-xl
                       px-4 py-3 text-center font-body text-sm text-dnd-crimson-bright"
            initial={{ opacity: 0, y: 20, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            transition={{ type: 'spring', stiffness: 320, damping: 26 }}
          >
            {warningText}
          </Pressable>
        )}
      </AnimatePresence>
    </>
  )
}

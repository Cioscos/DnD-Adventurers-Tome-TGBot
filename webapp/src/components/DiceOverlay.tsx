import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, matchPath } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { m, AnimatePresence } from 'framer-motion'
import { Dices } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import DiceIcon from '@/components/ui/DiceIcon'
import { useCharacterStore } from '@/store/characterStore'
import { haptic } from '@/auth/telegram'
import { api } from '@/api/client'
import { useDiceAnimation } from '@/dice/useDiceAnimation'
import type { DiceKind } from '@/dice/types'

const KINDS: DiceKind[] = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20', 'd100']
const SIDES_FOR = {
  d4: 4, d6: 6, d8: 8, d10: 10, d12: 12, d20: 20, d100: 100,
} as const satisfies Record<DiceKind, number>
const TOAST_DISMISS_MS = 3000

type DicePool = Partial<Record<DiceKind, number>>

type RollGroup = { kind: DiceKind; notation: string; rolls: number[]; total: number }

function useOverlayVisibility(): { visible: boolean; charId: number | null } {
  const location = useLocation()
  const activeCharId = useCharacterStore((s) => s.activeCharId)

  return useMemo(() => {
    const path = location.pathname
    if (matchPath('/char/:id/dice', path)) return { visible: false, charId: null }

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
  const [open, setOpen] = useState(false)
  const [pool, setPool] = useState<DicePool>({})

  const [results, setResults] = useState<RollGroup[] | null>(null)
  const [resultVisible, setResultVisible] = useState(false)
  const [errorVisible, setErrorVisible] = useState(false)

  const dismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const longPressFiredRef = useRef(false)

  useEffect(() => {
    return () => {
      if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current)
      if (longPressTimerRef.current) clearTimeout(longPressTimerRef.current)
    }
  }, [])

  const showResults = useCallback((groups: RollGroup[]) => {
    setResults(groups)
    setResultVisible(true)
    setErrorVisible(false)
    if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current)
    dismissTimerRef.current = setTimeout(() => setResultVisible(false), TOAST_DISMISS_MS)
  }, [])

  const dismissResults = useCallback(() => {
    if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current)
    setResultVisible(false)
  }, [])

  const showError = useCallback(() => {
    setErrorVisible(true)
    setResultVisible(false)
    if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current)
    dismissTimerRef.current = setTimeout(() => setErrorVisible(false), TOAST_DISMISS_MS)
  }, [])

  const dismissError = useCallback(() => {
    if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current)
    setErrorVisible(false)
  }, [])

  const dice = useDiceAnimation()
  const qc = useQueryClient()

  const rollMutation = useMutation({
    mutationFn: async (entries: Array<[DiceKind, number]>) => {
      if (!charId) throw new Error('no charId')
      const responses = await Promise.all(
        entries.map(([kind, count]) => api.dice.roll(charId, count, kind))
      )
      return entries.map(([kind], i) => {
        const r = responses[i]
        return { kind, notation: r.notation, rolls: r.rolls, total: r.total } as RollGroup
      })
    },
    onSuccess: async (groups) => {
      await dice.play({
        groups: groups.map((g) => ({ kind: g.kind, results: g.rolls })),
        interGroupMs: 150,
      })
      setPool({})
      setOpen(false)
      haptic.medium()
      showResults(groups)
    },
    onError: () => {
      haptic.error()
      showError()
    },
    onSettled: () => {
      if (charId) qc.invalidateQueries({ queryKey: ['dice-history', charId] })
    },
  })

  const entries = useMemo(
    () => (Object.entries(pool) as Array<[DiceKind, number]>).filter(([, n]) => n > 0),
    [pool]
  )
  const poolTotal = entries.reduce((s, [, n]) => s + n, 0)
  const isRolling = rollMutation.isPending

  const handleRoll = useCallback(() => {
    if (!entries.length || isRolling || !charId) return
    rollMutation.mutate(entries)
  }, [entries, isRolling, charId, rollMutation])

  const increment = useCallback((kind: DiceKind) => {
    haptic.light()
    setPool((p) => ({ ...p, [kind]: (p[kind] ?? 0) + 1 }))
  }, [])

  const clearKind = useCallback((kind: DiceKind) => {
    haptic.medium()
    setPool((p) => {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
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
  }, [])

  if (!visible) return null

  return (
    <>
    <div className="fixed bottom-4 right-4 z-[55]">
      {/* Sidebar kind buttons — appears above the FAB */}
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
                <m.button
                  key={kind}
                  type="button"
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
                                     rounded-full bg-dnd-crimson text-white text-[11px]
                                     font-bold font-mono flex items-center justify-center
                                     border border-dnd-surface-raised">
                      {count}
                    </span>
                  )}
                </m.button>
              )
            })}
          </m.div>
        )}
      </AnimatePresence>

      {/* Lancia button — appears to the left of the FAB when pool is not empty */}
      <AnimatePresence>
        {poolTotal > 0 && (
          <m.button
            type="button"
            onClick={handleRoll}
            disabled={isRolling}
            className="absolute right-full top-0 mr-2 h-14 px-5 rounded-2xl
                       bg-gradient-to-r from-dnd-gold-deep to-dnd-gold-bright
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
          </m.button>
        )}
      </AnimatePresence>

      {/* FAB */}
      <m.button
        type="button"
        aria-label={open ? t('character.dice_overlay.close') : t('character.dice_overlay.open')}
        onClick={toggleOpen}
        className="w-14 h-14 rounded-full
                   bg-gradient-to-br from-dnd-gold-deep to-dnd-gold-bright
                   border border-dnd-gold-dim shadow-halo-gold
                   flex items-center justify-center text-dnd-ink"
        whileTap={{ scale: 0.9 }}
        whileHover={{ scale: 1.05 }}
        initial={{ opacity: 0, scale: 0.6 }}
        animate={{ opacity: 1, scale: 1, rotate: open ? 45 : 0 }}
        transition={{ type: 'spring', stiffness: 260, damping: 22 }}
      >
        <Dices size={26} />
      </m.button>
    </div>

    {/* Result overlay bottom-center */}
    <AnimatePresence onExitComplete={() => setResults(null)}>
      {resultVisible && results && results.length > 0 && (
        <m.button
          type="button"
          onClick={dismissResults}
          className="fixed bottom-24 left-1/2 -translate-x-1/2 z-[55]
                     max-w-xs w-[calc(100%-2rem)]
                     rounded-2xl bg-dnd-surface-raised/95 backdrop-blur-md
                     border border-dnd-gold-dim shadow-parchment-xl
                     px-4 py-3 text-left"
          initial={{ opacity: 0, y: 20, scale: 0.9 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 10, scale: 0.95 }}
          transition={{ type: 'spring', stiffness: 320, damping: 26 }}
        >
          <div className="space-y-1">
            {results.map((g, i) => (
              <div key={i} className="flex items-baseline justify-between gap-2 font-mono text-sm">
                <span className="text-dnd-gold-dim">
                  {g.notation}
                  {g.rolls.length > 1 && (
                    <span className="text-dnd-text-faint text-xs ml-1">
                      [{g.rolls.join('+')}]
                    </span>
                  )}
                </span>
                <span className="font-display font-black text-dnd-gold-bright text-lg">
                  {g.total}
                </span>
              </div>
            ))}
          </div>
        </m.button>
      )}
    </AnimatePresence>

    {/* Error toast bottom-center */}
    <AnimatePresence>
      {errorVisible && (
        <m.button
          type="button"
          role="alert"
          onClick={dismissError}
          className="fixed bottom-24 left-1/2 -translate-x-1/2 z-[55]
                     max-w-xs w-[calc(100%-2rem)]
                     rounded-2xl bg-dnd-surface-raised/95 backdrop-blur-md
                     border border-dnd-crimson shadow-parchment-xl
                     px-4 py-3 text-center font-body text-sm text-dnd-crimson-bright"
          initial={{ opacity: 0, y: 20, scale: 0.9 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 10, scale: 0.95 }}
          transition={{ type: 'spring', stiffness: 320, damping: 26 }}
        >
          {t('character.dice_overlay.roll_failed')}
        </m.button>
      )}
    </AnimatePresence>
    </>
  )
}

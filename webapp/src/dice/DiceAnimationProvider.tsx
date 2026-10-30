import {
  createContext,
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { useTranslation } from 'react-i18next'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import { useDeferredBlur } from '@/hooks/useDeferredBlur'
import { useDiceSettings } from '@/store/diceSettings'
import type { DiceAnimationApi, PlayCollectGroup, DetectedResult } from './types'
import type { SceneRequest } from './DiceScene'
import { DicePackProvider } from './packs/DicePackProvider'
import DiceErrorBoundary from './DiceErrorBoundary'
import { schedulePreloadDiceScene } from './preload'
import { rollMany } from './rng'

const DiceScene = lazy(() => import('./DiceScene'))

const DiceAnimationContext = createContext<DiceAnimationApi | null>(null)

/** Oltre questo numero i dadi si ammucchiano e le facce non si leggono più. */
const MAX_ANIMATED_DICE = 12
/** Rete lenta: se la scena non arriva, il tiro non resta in attesa. */
const SCENE_LOAD_TIMEOUT_MS = 8000
const OVERLAY_FADE_MS = 180

const bodiesPerRoll = (g: PlayCollectGroup) => (g.kind === 'd100' ? 2 : 1)

/** Distribuisce il tetto a turno tra i gruppi, così nessun tipo di dado resta fuori. */
function capForAnimation(groups: PlayCollectGroup[]): PlayCollectGroup[] {
  const counts = groups.map(() => 0)
  let room = MAX_ANIMATED_DICE
  let added = true
  while (added) {
    added = false
    groups.forEach((g, i) => {
      if (counts[i] < g.count && bodiesPerRoll(g) <= room) {
        counts[i] += 1
        room -= bodiesPerRoll(g)
        added = true
      }
    })
  }
  return groups.map((g, i) => ({ ...g, count: counts[i] }))
}

/** Risultati animati, completati in locale fino al numero di dadi richiesto. */
function completeResults(groups: PlayCollectGroup[], detected: DetectedResult[]): DetectedResult[] {
  return groups.flatMap((g, groupIndex) => {
    const animated = detected.filter((d) => d.groupIndex === groupIndex)
    const missingRolls = g.count - Math.ceil(animated.length / bodiesPerRoll(g))
    const rest = rollMany(g.kind, missingRolls).map((r) => ({ groupIndex, ...r }))
    return [...animated, ...rest]
  })
}

export default function DiceAnimationProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const reducedMotion = useReducedMotion()
  const animate3d = useDiceSettings((s) => s.animate3d)
  const shouldAnimate = !reducedMotion && animate3d

  const [shouldMountScene, setShouldMountScene] = useState(false)
  const [sceneRequest, setSceneRequest] = useState<SceneRequest | null>(null)
  const [overlayVisible, setOverlayVisible] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [skipToken, setSkipToken] = useState(0)
  const { blurStyle, onEntranceComplete } = useDeferredBlur(overlayVisible)

  const sceneReadyRef = useRef(false)
  const sceneFailedRef = useRef(false)
  const readyWaitersRef = useRef<Array<(ready: boolean) => void>>([])
  const requestIdRef = useRef(0)
  const pendingCompleteRef = useRef<((results: DetectedResult[]) => void) | null>(null)
  const queueRef = useRef<Promise<unknown>>(Promise.resolve())

  useEffect(() => {
    if (shouldAnimate) schedulePreloadDiceScene()
  }, [shouldAnimate])

  const settleWaiters = (ready: boolean) => {
    for (const cb of readyWaitersRef.current) cb(ready)
    readyWaitersRef.current = []
  }

  const handleSceneMount = useCallback(() => {
    sceneReadyRef.current = true
    settleWaiters(true)
  }, [])

  // WebGL assente o chunk non scaricabile: per il resto della sessione i tiri
  // si generano in locale, senza riprovare una scena che fallirebbe di nuovo.
  const handleSceneError = useCallback((error: Error) => {
    console.warn('[dice] scena 3D non disponibile', error)
    sceneFailedRef.current = true
    sceneReadyRef.current = false
    settleWaiters(false)
    pendingCompleteRef.current?.([])
    pendingCompleteRef.current = null
    setOverlayVisible(false)
    setSceneRequest(null)
    setIsPlaying(false)
    setShouldMountScene(false)
  }, [])

  const waitForScene = useCallback(
    () =>
      sceneReadyRef.current
        ? Promise.resolve(true)
        : new Promise<boolean>((resolve) => {
            readyWaitersRef.current.push(resolve)
            setTimeout(() => resolve(false), SCENE_LOAD_TIMEOUT_MS)
          }),
    [],
  )

  const animate = useCallback(
    async (groups: PlayCollectGroup[]): Promise<DetectedResult[]> => {
      setIsPlaying(true)
      setOverlayVisible(true)
      setShouldMountScene(true)
      const ready = await waitForScene()

      const detected = ready
        ? await new Promise<DetectedResult[]>((resolve) => {
            const done = (r: DetectedResult[]) => {
              pendingCompleteRef.current = null
              resolve(r)
            }
            pendingCompleteRef.current = done
            const id = ++requestIdRef.current
            setSceneRequest({ id, groups, onComplete: done })
          })
        : []

      setOverlayVisible(false)
      await new Promise((r) => setTimeout(r, OVERLAY_FADE_MS))
      setSceneRequest(null)
      setIsPlaying(false)
      return detected
    },
    [waitForScene],
  )

  const playAndCollect = useCallback(
    (groups: PlayCollectGroup[]): Promise<DetectedResult[]> => {
      if (groups.length === 0) return Promise.resolve([])
      // Una scena sola: i tiri ravvicinati si mettono in fila, nessuno si perde.
      const run = queueRef.current.then(async () => {
        if (!shouldAnimate || sceneFailedRef.current) return completeResults(groups, [])
        return completeResults(groups, await animate(capForAnimation(groups)))
      })
      queueRef.current = run.catch(() => {})
      return run
    },
    [animate, shouldAnimate],
  )

  const api = useMemo<DiceAnimationApi>(
    () => ({ playAndCollect, isPlaying }),
    [playAndCollect, isPlaying],
  )

  return (
    <DicePackProvider>
      <DiceAnimationContext.Provider value={api}>
        {children}
        {shouldMountScene && (
          <div
            aria-hidden
            data-testid="dice-overlay"
            className="fixed inset-0 z-[60]"
            onClick={() => {
              if (overlayVisible) setSkipToken((v) => v + 1)
            }}
            onTransitionEnd={(e) => {
              // target === currentTarget: onTransitionEnd fa bubbling, senza
              // questa guardia la transizione di opacity di un discendente
              // (es. dentro DiceScene) risalirebbe fino a qui e segnerebbe
              // l'ingresso completato in anticipo (review Minor #1).
              if (e.target === e.currentTarget && e.propertyName === 'opacity' && overlayVisible) {
                onEntranceComplete()
              }
            }}
            style={{
              opacity: overlayVisible ? 1 : 0,
              // Attivo solo durante il tiro: il tocco salta l'animazione e non
              // arriva ai pulsanti sotto.
              pointerEvents: overlayVisible ? 'auto' : 'none',
              transition: `opacity ${OVERLAY_FADE_MS}ms ease-out`,
              background: overlayVisible ? 'var(--dnd-overlay)' : 'transparent',
              ...blurStyle,
              willChange: 'opacity',
            }}
          >
            <DiceErrorBoundary onError={handleSceneError}>
              <Suspense fallback={null}>
                <DiceScene request={sceneRequest} onMount={handleSceneMount} skipToken={skipToken} />
              </Suspense>
            </DiceErrorBoundary>
            <p className="absolute inset-x-0 bottom-8 text-center text-xs font-cinzel uppercase tracking-widest text-dnd-parchment/80 pointer-events-none">
              {t('character.dice.tap_to_skip')}
            </p>
          </div>
        )}
      </DiceAnimationContext.Provider>
    </DicePackProvider>
  )
}

export { DiceAnimationContext }

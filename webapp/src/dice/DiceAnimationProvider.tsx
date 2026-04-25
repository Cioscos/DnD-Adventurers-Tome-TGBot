import {
  createContext,
  lazy,
  Suspense,
  useCallback,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import { useDiceSettings } from '@/store/diceSettings'
import type { DiceAnimationApi, DicePlayRequest } from './types'
import type { SceneRequest } from './DiceScene'

const DiceScene = lazy(() => import('./DiceScene'))

const DiceAnimationContext = createContext<DiceAnimationApi | null>(null)

export function DiceAnimationContextExport() {
  return DiceAnimationContext
}

export default function DiceAnimationProvider({ children }: { children: ReactNode }) {
  const reducedMotion = useReducedMotion()
  const animate3d = useDiceSettings((s) => s.animate3d)
  const shouldAnimate = !reducedMotion && animate3d

  const [shouldMountScene, setShouldMountScene] = useState(false)
  const [sceneRequest, setSceneRequest] = useState<SceneRequest | null>(null)
  const [overlayVisible, setOverlayVisible] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)

  const sceneReadyRef = useRef(false)
  const readyWaitersRef = useRef<Array<() => void>>([])
  const requestIdRef = useRef(0)

  const handleSceneMount = useCallback(() => {
    sceneReadyRef.current = true
    for (const cb of readyWaitersRef.current) cb()
    readyWaitersRef.current = []
  }, [])

  const waitForScene = useCallback(
    () =>
      sceneReadyRef.current
        ? Promise.resolve()
        : new Promise<void>((resolve) => readyWaitersRef.current.push(resolve)),
    [],
  )

  const play = useCallback(
    async (req: DicePlayRequest) => {
      if (!shouldAnimate) return
      if (!req.groups.length) return

      setIsPlaying(true)
      setOverlayVisible(true)
      setShouldMountScene(true)
      await waitForScene()

      for (const group of req.groups) {
        const id = ++requestIdRef.current
        await new Promise<void>((resolve) => {
          setSceneRequest({ id, group, onComplete: (_results) => resolve() })
        })
        if (req.interGroupMs && req.interGroupMs > 0) {
          await new Promise((r) => setTimeout(r, req.interGroupMs))
        }
      }

      setOverlayVisible(false)
      await new Promise((r) => setTimeout(r, 180))
      setSceneRequest(null)
      setIsPlaying(false)
    },
    [shouldAnimate, waitForScene],
  )

  const api = useMemo<DiceAnimationApi>(() => ({ play, isPlaying }), [play, isPlaying])

  return (
    <DiceAnimationContext.Provider value={api}>
      {children}
      {shouldMountScene && (
        <div
          aria-hidden
          className="fixed inset-0 z-[60]"
          style={{
            opacity: overlayVisible ? 1 : 0,
            pointerEvents: 'none',
            transition: 'opacity 180ms ease-out',
            background: overlayVisible ? 'var(--dnd-overlay)' : 'transparent',
            backdropFilter: overlayVisible ? 'blur(6px)' : 'none',
            WebkitBackdropFilter: overlayVisible ? 'blur(6px)' : 'none',
            willChange: 'opacity',
          }}
        >
          <Suspense fallback={null}>
            <DiceScene request={sceneRequest} onMount={handleSceneMount} />
          </Suspense>
        </div>
      )}
    </DiceAnimationContext.Provider>
  )
}

export { DiceAnimationContext }

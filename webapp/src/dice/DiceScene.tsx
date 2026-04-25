import { useEffect, useRef, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { ContactShadows } from '@react-three/drei'
import * as THREE from 'three'
import * as CANNON from 'cannon-es'
import type { DiceGroup, DiceKind, DiceTint, DetectedResult } from './types'
import { getDiceGeometry } from './geometries'
import { getDiceMaterial, getNumeralMaterial } from './materials'
import { createDiceWorld, updateWalls, type DiceWorld } from './physics/world'
import { spawnDiceBody, computeSpawnPositions, totalKineticActivity } from './physics/spawner'
import { faceUp } from './physics/faceDetector'
import { PHYSICS } from './physics/constants'
import { useDicePack } from './packs/DicePackProvider'
import { getTintOverride } from './packs/manifest'

export type SceneRequest = {
  id: number
  groups: DiceGroup[]
  onComplete: (results: DetectedResult[]) => void
}

type Phase = 'idle' | 'simulating' | 'reading' | 'holding'

interface Entity {
  body: CANNON.Body
  group: THREE.Group | null
  detectedValue: number | null
  retries: number
  kind: Exclude<DiceKind, 'd100'>
  groupIndex: number
  tint: DiceTint
}

const PLANE_GEOMETRY = new THREE.PlaneGeometry(1, 1)

type Props = {
  request: SceneRequest | null
  onMount?: () => void
}

export default function DiceScene({ request, onMount }: Props) {
  return (
    <Canvas
      dpr={[1, 1.5]}
      gl={{ alpha: true, antialias: true }}
      camera={{ position: [0, 5.5, 1.8], fov: 42, near: 0.1, far: 30 }}
      onCreated={({ camera }) => camera.lookAt(0, 0, 0)}
      shadows
      frameloop="demand"
      style={{
        width: '100%',
        height: '100%',
        touchAction: 'none',
        pointerEvents: 'none',
      }}
    >
      <ambientLight intensity={0.65} />
      <directionalLight
        position={[2.5, 5, 2.5]}
        intensity={1.3}
        castShadow
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
        shadow-camera-left={-1.6}
        shadow-camera-right={1.6}
        shadow-camera-top={1.6}
        shadow-camera-bottom={-1.6}
      />
      <ContactShadows
        position={[0, -0.88, 0]}
        opacity={0.55}
        scale={4.5}
        blur={2.4}
        far={2}
        resolution={512}
      />
      <CameraFit />
      <Orchestrator request={request} onMount={onMount} />
    </Canvas>
  )
}

function CameraFit() {
  const { camera, size } = useThree()
  useEffect(() => {
    if (!(camera instanceof THREE.PerspectiveCamera)) return
    const aspect = size.width / Math.max(size.height, 1)
    camera.aspect = aspect
    camera.updateProjectionMatrix()
  }, [camera, size.width, size.height])
  return null
}

function Orchestrator({ request, onMount }: Props) {
  const worldRef = useRef<DiceWorld | null>(null)
  if (!worldRef.current) worldRef.current = createDiceWorld()

  const entitiesRef = useRef<Entity[]>([])
  const phaseRef = useRef<Phase>('idle')
  const phaseStartRef = useRef<number>(0)
  const lowEnergyMsRef = useRef<number>(0)
  const [version, setVersion] = useState(0)
  const { invalidate, camera, size } = useThree()
  const { pack } = useDicePack()
  const onMountRef = useRef(onMount)
  onMountRef.current = onMount

  const onCompleteRef = useRef<((results: DetectedResult[]) => void) | undefined>(undefined)
  useEffect(() => {
    onCompleteRef.current = request?.onComplete
  }, [request])

  useEffect(() => {
    if (!(camera instanceof THREE.PerspectiveCamera)) return
    updateWalls(worldRef.current!, camera, size)
  }, [camera, size.width, size.height])

  useEffect(() => {
    onMountRef.current?.()
  }, [])

  useEffect(() => {
    if (!request) return
    const world = worldRef.current!.world

    for (const e of entitiesRef.current) world.removeBody(e.body)
    entitiesRef.current = []

    // count total bodies across all groups (d100 = 2 d10 bodies)
    const groupSpec = request.groups.map((g) => {
      const kindBase: Exclude<DiceKind, 'd100'> = g.kind === 'd100' ? 'd10' : g.kind
      const bodyCount = g.kind === 'd100' ? 2 : g.results?.length ?? g.count ?? 1
      return { kindBase, bodyCount, tint: g.tint ?? 'normal' }
    })
    const totalBodies = groupSpec.reduce((s, g) => s + g.bodyCount, 0)
    const positions = computeSpawnPositions(totalBodies)

    const entities: Entity[] = []
    let posIdx = 0
    for (let gi = 0; gi < groupSpec.length; gi++) {
      const { kindBase, bodyCount, tint } = groupSpec[gi]
      const geomData = getDiceGeometry(kindBase)
      for (let i = 0; i < bodyCount; i++) {
        const body = spawnDiceBody({
          shape: geomData.shape,
          material: worldRef.current!.diceMaterial,
          position: positions[posIdx++],
          totalCount: totalBodies,
        })
        world.addBody(body)
        entities.push({
          body,
          group: null,
          detectedValue: null,
          retries: 0,
          kind: kindBase,
          groupIndex: gi,
          tint,
        })
      }
    }
    entitiesRef.current = entities
    phaseRef.current = 'simulating'
    phaseStartRef.current = performance.now()
    lowEnergyMsRef.current = 0
    setVersion((v) => v + 1)

    let raf = 0
    const tick = () => {
      invalidate()
      if (phaseRef.current !== 'idle') raf = requestAnimationFrame(tick)
    }
    tick()
    return () => cancelAnimationFrame(raf)
  }, [request, invalidate])

  useFrame(() => {
    if (phaseRef.current === 'idle') return
    const now = performance.now()
    const elapsed = now - phaseStartRef.current
    const world = worldRef.current!.world

    if (phaseRef.current === 'simulating') {
      world.step(1 / 60)
      for (const e of entitiesRef.current) {
        if (e.group) {
          e.group.position.set(e.body.position.x, e.body.position.y, e.body.position.z)
          e.group.quaternion.set(
            e.body.quaternion.x,
            e.body.quaternion.y,
            e.body.quaternion.z,
            e.body.quaternion.w,
          )
        }
      }
      const allSleeping = entitiesRef.current.every(
        (e) => e.body.sleepState === CANNON.Body.SLEEPING,
      )
      const timedOut = elapsed > PHYSICS.simulationHardTimeoutMs

      // Force-sleep su attività cinetica bassa sostenuta.
      // Soglia per body, scala con numero dadi (più dadi = soglia più tollerante).
      const n = entitiesRef.current.length
      const perBodyThreshold = n <= 3 ? 0.08 : n <= 8 ? 0.18 : 0.35
      const totalThreshold = perBodyThreshold * n
      const activity = totalKineticActivity(entitiesRef.current.map((e) => e.body))
      if (activity < totalThreshold) {
        lowEnergyMsRef.current += 1000 / 60
      } else {
        lowEnergyMsRef.current = 0
      }
      const lowEnergyTimeout = n <= 3 ? 600 : 350
      const stalled = lowEnergyMsRef.current >= lowEnergyTimeout

      if (allSleeping || timedOut || stalled) {
        if (timedOut || stalled) for (const e of entitiesRef.current) e.body.sleep()
        lowEnergyMsRef.current = 0
        phaseRef.current = 'reading'
        phaseStartRef.current = now
      }
      return
    }

    if (phaseRef.current === 'reading') {
      const COS_15 = Math.cos((15 * Math.PI) / 180)
      const MAX_RETRIES = 2
      let needRetry = false
      for (const e of entitiesRef.current) {
        if (e.detectedValue !== null) continue
        const geomData = getDiceGeometry(e.kind)
        const q = new THREE.Quaternion(
          e.body.quaternion.x,
          e.body.quaternion.y,
          e.body.quaternion.z,
          e.body.quaternion.w,
        )
        const { value, dot } = faceUp(geomData.faceNormals, q)
        if (dot < COS_15 && e.retries < MAX_RETRIES) {
          // ambiguo: nudge + re-simulate
          e.body.wakeUp()
          e.body.applyImpulse(
            new CANNON.Vec3((Math.random() - 0.5) * 0.4, -0.3, (Math.random() - 0.5) * 0.4),
            new CANNON.Vec3(0, 0.1, 0),
          )
          e.body.angularVelocity.set(
            (Math.random() - 0.5) * 4,
            (Math.random() - 0.5) * 4,
            (Math.random() - 0.5) * 4,
          )
          e.retries += 1
          needRetry = true
        } else {
          e.detectedValue = value
        }
      }
      if (needRetry) {
        phaseRef.current = 'simulating'
        phaseStartRef.current = now
      } else {
        phaseRef.current = 'holding'
        phaseStartRef.current = now
      }
      return
    }

    if (phaseRef.current === 'holding') {
      const HOLD_MS = 1500
      const LIFT_IN = 220
      const LIFT_OUT = 300
      const SCALE_BOOST = 0.22
      let progress: number
      if (elapsed < LIFT_IN) {
        const t = elapsed / LIFT_IN
        progress = 1 - Math.pow(1 - t, 2)
      } else if (elapsed < HOLD_MS - LIFT_OUT) {
        progress = 1
      } else {
        const t = Math.min(1, (elapsed - (HOLD_MS - LIFT_OUT)) / LIFT_OUT)
        progress = 1 - (1 - Math.pow(1 - t, 2))
      }
      const scale = 1 + SCALE_BOOST * progress
      entitiesRef.current.forEach((e) => {
        if (!e.group) return
        e.group.scale.setScalar(scale)
      })
      if (elapsed > HOLD_MS) {
        phaseRef.current = 'idle'
        const results: DetectedResult[] = entitiesRef.current.map((e) => ({
          groupIndex: e.groupIndex,
          kind: e.kind,
          value: e.detectedValue ?? 1,
        }))
        onCompleteRef.current?.(results)
      }
    }
  })

  const entities = entitiesRef.current
  const skipNumerals = pack?.manifest.numerals === 'embedded'

  return (
    <>
      {entities.map((e, i) => {
        const geomData = getDiceGeometry(e.kind)
        const baseMaterial = getDiceMaterial(e.tint, pack, e.kind)
        const override = pack ? getTintOverride(pack.manifest, e.tint) : undefined
        return (
          <group
            key={`${version}-${i}`}
            ref={(g: THREE.Group | null) => {
              e.group = g
            }}
          >
            <mesh geometry={geomData.geometry} material={baseMaterial} castShadow receiveShadow />
            {!skipNumerals &&
              geomData.faceFrames.map((ff) => {
                // inradius*1.7 is the heuristic for regular polygons; cap at the
                // largest centered square that actually fits inside the face so
                // numeral corners do not bleed past kite apexes / triangle vertices.
                const planeSize = Math.min(ff.inradius * 1.7, ff.maxNumeralHalfSide * 2 * 0.95)
                return (
                  <mesh
                    key={ff.value}
                    geometry={PLANE_GEOMETRY}
                    material={getNumeralMaterial(String(ff.value), e.tint, override)}
                    position={ff.offsetPosition.toArray()}
                    quaternion={[ff.quaternion.x, ff.quaternion.y, ff.quaternion.z, ff.quaternion.w]}
                    scale={planeSize}
                  />
                )
              })}
          </group>
        )
      })}
    </>
  )
}

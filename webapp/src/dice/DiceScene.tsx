import { useEffect, useRef, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { ContactShadows } from '@react-three/drei'
import * as THREE from 'three'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import * as CANNON from 'cannon-es'
import type { DiceGroup, DiceKind, DiceTint, DetectedResult } from './types'
import { getDiceGeometry } from './geometries'
import { getDiceMaterial, getNumeralMaterial } from './materials'
import { createDiceWorld, updateWalls, type DiceWorld } from './physics/world'
import { spawnDiceBody, computeSpawnPositions, totalKineticActivity } from './physics/spawner'
import { faceUp } from './physics/faceDetector'
import { PHYSICS } from './physics/constants'
import { useDicePack } from './packs/dicePackContext'
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

/**
 * Separa le coppie di dadi rimaste compenetrate (centri a distanza < diametro)
 * con un impulso lungo la congiungente. Ritorna true se ha trovato overlap.
 */
function separateOverlaps(entities: Entity[]): boolean {
  let found = false
  const dir = new CANNON.Vec3()
  for (let i = 0; i < entities.length; i++) {
    for (let j = i + 1; j < entities.length; j++) {
      const a = entities[i].body
      const b = entities[j].body
      b.position.vsub(a.position, dir)
      const dist = dir.length()
      if (dist >= 0.6) continue
      found = true
      if (dist < 1e-4) dir.set(1, 0, 0)
      else dir.scale(1 / dist, dir)
      a.wakeUp()
      b.wakeUp()
      b.applyImpulse(new CANNON.Vec3(dir.x * 0.6, 0.25, dir.z * 0.6))
      a.applyImpulse(new CANNON.Vec3(-dir.x * 0.6, 0.25, -dir.z * 0.6))
    }
  }
  return found
}

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
      <ambientLight intensity={0.25} />
      <hemisphereLight args={['#ffe8c8', '#2e2014', 0.55]} />
      <directionalLight
        position={[2.5, 5, 2.5]}
        intensity={2.0}
        castShadow
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
        shadow-camera-left={-2.4}
        shadow-camera-right={2.4}
        shadow-camera-top={2.4}
        shadow-camera-bottom={-2.4}
        shadow-normalBias={0.02}
      />
      {/* fill laterale contrapposta alla key: senza una luce radente il
          rilievo delle normal map dei pack non si percepisce */}
      <directionalLight position={[-3, 2.5, -2]} intensity={0.6} />
      <ContactShadows
        position={[0, -0.88, 0]}
        opacity={0.55}
        scale={6}
        blur={2.4}
        far={2.5}
        resolution={512}
      />
      <SceneEnvironment />
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

/**
 * Environment map procedurale (RoomEnvironment, bundled in three): dà senso a
 * metalness/envMapIntensity dei pack — un materiale metallico senza envmap
 * rende solo più scuro.
 */
function SceneEnvironment() {
  const { gl, scene } = useThree()
  useEffect(() => {
    const pmrem = new THREE.PMREMGenerator(gl)
    const room = new RoomEnvironment()
    const envTarget = pmrem.fromScene(room, 0.04)
    scene.environment = envTarget.texture
    room.dispose()
    pmrem.dispose()
    return () => {
      scene.environment = null
      envTarget.dispose()
    }
  }, [gl, scene])
  return null
}

function Orchestrator({ request, onMount }: Props) {
  const worldRef = useRef<DiceWorld | null>(null)
  if (!worldRef.current) worldRef.current = createDiceWorld()

  const entitiesRef = useRef<Entity[]>([])
  const phaseRef = useRef<Phase>('idle')
  const phaseStartRef = useRef<number>(0)
  const lowEnergyMsRef = useRef<number>(0)
  const repairUsedRef = useRef<boolean>(false)
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
  }, [camera, size])

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
    const positions = computeSpawnPositions(totalBodies, worldRef.current!)

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
    repairUsedRef.current = false
    setVersion((v) => v + 1)

    let raf = 0
    const tick = () => {
      invalidate()
      if (phaseRef.current !== 'idle') raf = requestAnimationFrame(tick)
    }
    tick()
    return () => cancelAnimationFrame(raf)
  }, [request, invalidate])

  useFrame((_, delta) => {
    if (phaseRef.current === 'idle') return
    const now = performance.now()
    const elapsed = now - phaseStartRef.current
    const world = worldRef.current!.world

    if (phaseRef.current === 'simulating') {
      // Substep fissi + accumulator: tempo reale anche a 120 Hz e penetrazione
      // per step dimezzata. Il clamp del delta copre i gap di idle del canvas.
      world.step(PHYSICS.fixedTimeStep, Math.min(delta, 1 / 15), PHYSICS.maxSubSteps)
      for (const e of entitiesRef.current) {
        if (e.group) {
          const p = e.body.interpolatedPosition
          const q = e.body.interpolatedQuaternion
          e.group.position.set(p.x, p.y, p.z)
          e.group.quaternion.set(q.x, q.y, q.z, q.w)
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
        lowEnergyMsRef.current += delta * 1000
      } else {
        lowEnergyMsRef.current = 0
      }
      const lowEnergyTimeout = n <= 3 ? 700 : 500
      const stalled = lowEnergyMsRef.current >= lowEnergyTimeout

      if (allSleeping || timedOut || stalled) {
        // Pila ferma ma ancora sovrapposta? Un solo tentativo di separazione
        // prima di congelare i dadi compenetrati.
        if (stalled && !timedOut && !repairUsedRef.current) {
          repairUsedRef.current = true
          if (separateOverlaps(entitiesRef.current)) {
            lowEnergyMsRef.current = 0
            return
          }
        }
        if (timedOut || stalled) for (const e of entitiesRef.current) e.body.sleep()
        lowEnergyMsRef.current = 0
        // Allinea i gruppi allo stato raw: l'interpolazione può restare un
        // substep indietro e la lettura/holding usa lo stato canonico.
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
          // ambiguo (dado in pendenza, tipicamente appoggiato a un muro):
          // spintarella verso il centro arena + leggero lift, così cade piatto
          e.body.wakeUp()
          const px = e.body.position.x
          const pz = e.body.position.z
          const len = Math.hypot(px, pz) || 1
          e.body.applyImpulse(new CANNON.Vec3((-px / len) * 0.8, 1.0, (-pz / len) * 0.8))
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
              geomData.faceFrames.map((ff, frameIdx) => (
                <mesh
                  key={frameIdx}
                  geometry={PLANE_GEOMETRY}
                  material={getNumeralMaterial(String(ff.value), e.tint, override)}
                  position={ff.offsetPosition.toArray()}
                  quaternion={[ff.quaternion.x, ff.quaternion.y, ff.quaternion.z, ff.quaternion.w]}
                  scale={ff.size}
                />
              ))}
          </group>
        )
      })}
    </>
  )
}

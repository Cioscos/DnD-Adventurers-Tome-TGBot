import { useEffect, useRef, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { ContactShadows } from '@react-three/drei'
import * as THREE from 'three'
import * as CANNON from 'cannon-es'
import type { DiceGroup, DiceKind } from './types'
import { getDiceGeometry } from './geometries'
import { getDiceMaterial, getNumeralMaterial } from './materials'
import { createDiceWorld, updateWalls, type DiceWorld } from './physics/world'
import { spawnDiceBody, computeSpawnPositions } from './physics/spawner'
import { quaternionForFace } from './physics/faceDetector'

export type SceneRequest = { id: number; group: DiceGroup; onComplete: () => void }

type Phase = 'idle' | 'simulating' | 'snapping' | 'holding'

interface Entity {
  body: CANNON.Body
  group: THREE.Group | null
  targetFace: number
  kind: Exclude<DiceKind, 'd100'>
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
      camera={{ position: [0, 2.2, 2.4], fov: 70, near: 0.1, far: 30 }}
      onCreated={({ camera }) => camera.lookAt(0, -0.4, 0)}
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
    const targetHalfW = 1.15
    const dist = Math.hypot(camera.position.x, camera.position.y, camera.position.z)
    const halfH = targetHalfW / Math.max(aspect, 0.01)
    const fovV = (2 * Math.atan(halfH / dist) * 180) / Math.PI
    camera.fov = Math.min(Math.max(fovV, 42), 82)
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
  const snapFromRef = useRef<THREE.Quaternion[]>([])
  const snapToRef = useRef<THREE.Quaternion[]>([])
  const snapFromPosRef = useRef<THREE.Vector3[]>([])
  const snapToPosRef = useRef<THREE.Vector3[]>([])
  const [version, setVersion] = useState(0)
  const { invalidate, camera, size } = useThree()
  const onMountRef = useRef(onMount)
  onMountRef.current = onMount

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

    const group = request.group
    const kindBase: Exclude<DiceKind, 'd100'> = group.kind === 'd100' ? 'd10' : group.kind
    const geomData = getDiceGeometry(kindBase)

    const bodyTargets: number[] = []
    for (const result of group.results) {
      if (group.kind === 'd100') {
        const tens = Math.floor(result / 10)
        const ones = result % 10
        bodyTargets.push(tens === 0 ? 10 : tens)
        bodyTargets.push(ones === 0 ? 10 : ones)
      } else {
        bodyTargets.push(result)
      }
    }

    const positions = computeSpawnPositions(bodyTargets.length)
    const entities: Entity[] = []
    for (let i = 0; i < bodyTargets.length; i++) {
      const body = spawnDiceBody({
        shape: geomData.shape,
        material: worldRef.current!.diceMaterial,
        position: positions[i],
      })
      world.addBody(body)
      entities.push({ body, group: null, targetFace: bodyTargets[i], kind: kindBase })
    }
    entitiesRef.current = entities
    phaseRef.current = 'simulating'
    phaseStartRef.current = performance.now()
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
      const allSleeping = entitiesRef.current.every((e) => e.body.sleepState === CANNON.Body.SLEEPING)
      if (allSleeping || elapsed > 2400) {
        const LIFT_Y = 0.1
        snapFromRef.current = entitiesRef.current.map(
          (e) =>
            new THREE.Quaternion(
              e.body.quaternion.x,
              e.body.quaternion.y,
              e.body.quaternion.z,
              e.body.quaternion.w,
            ),
        )
        snapFromPosRef.current = entitiesRef.current.map(
          (e) => new THREE.Vector3(e.body.position.x, e.body.position.y, e.body.position.z),
        )
        snapToPosRef.current = entitiesRef.current.map((e) => {
          const x = THREE.MathUtils.clamp(e.body.position.x, -0.5, 0.5)
          const z = THREE.MathUtils.clamp(e.body.position.z, -0.5, 0.5)
          return new THREE.Vector3(x, LIFT_Y, z)
        })
        snapToRef.current = entitiesRef.current.map((e, i) => {
          const geomData = getDiceGeometry(e.kind)
          const toCamera = new THREE.Vector3()
            .subVectors(camera.position, snapToPosRef.current[i])
            .normalize()
          return quaternionForFace(
            geomData.faceNormals,
            e.targetFace,
            snapFromRef.current[i],
            toCamera,
          )
        })
        phaseRef.current = 'snapping'
        phaseStartRef.current = now
      }
    } else if (phaseRef.current === 'snapping') {
      const duration = 520
      const t = Math.min(1, elapsed / duration)
      const eased = 1 - Math.pow(1 - t, 3)
      entitiesRef.current.forEach((e, i) => {
        const q = new THREE.Quaternion().slerpQuaternions(
          snapFromRef.current[i],
          snapToRef.current[i],
          eased,
        )
        const p = new THREE.Vector3().lerpVectors(
          snapFromPosRef.current[i],
          snapToPosRef.current[i],
          eased,
        )
        e.body.quaternion.set(q.x, q.y, q.z, q.w)
        e.body.position.set(p.x, p.y, p.z)
        if (e.group) {
          e.group.quaternion.copy(q)
          e.group.position.copy(p)
        }
      })
      if (t >= 1) {
        phaseRef.current = 'holding'
        phaseStartRef.current = now
      }
    } else if (phaseRef.current === 'holding') {
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
        request?.onComplete()
      }
    }
  })

  const entities = entitiesRef.current
  const tint = request?.group.tint ?? 'normal'
  const baseMaterial = getDiceMaterial(tint)

  return (
    <>
      {entities.map((e, i) => {
        const geomData = getDiceGeometry(e.kind)
        return (
          <group
            key={`${version}-${i}`}
            ref={(g: THREE.Group | null) => {
              e.group = g
            }}
          >
            <mesh geometry={geomData.geometry} material={baseMaterial} castShadow receiveShadow />
            {geomData.faceFrames.map((ff) => {
              const planeSize = ff.inradius * 1.7
              return (
                <mesh
                  key={ff.value}
                  geometry={PLANE_GEOMETRY}
                  material={getNumeralMaterial(String(ff.value), tint)}
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

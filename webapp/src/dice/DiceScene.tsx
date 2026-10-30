import { useEffect, useRef, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { ContactShadows } from '@react-three/drei'
import * as THREE from 'three'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import type { DiceGroup, DiceKind, DiceTint, DetectedResult } from './types'
import { getDiceGeometry } from './geometries'
import { getDiceMaterial, getNumeralMaterial } from './materials'
import { createDiceWorld, updateWalls, type DiceWorld } from './physics/world'
import { createRollSimulation, type RollSimulation, type SimDieSpec } from './physics/rollSimulation'
import { d100FaceLabel, type D100Role } from './d100'
import type { LoadedPack } from './packs/loader'
import { useDicePack } from './packs/dicePackContext'
import { getTintOverride } from './packs/manifest'

export type SceneRequest = {
  id: number
  groups: DiceGroup[]
  /** I dadi si sono fermati: inizia la pausa finale. */
  onSettled?: (results: DetectedResult[]) => void
  onComplete: (results: DetectedResult[]) => void
}

interface Entity {
  group: THREE.Group | null
  kind: Exclude<DiceKind, 'd100'>
  tint: DiceTint
  d100Role: D100Role | null
}

const PLANE_GEOMETRY = new THREE.PlaneGeometry(1, 1)

const HOLD_MS = 1500
const LIFT_IN = 220
const LIFT_OUT = 300
const SCALE_BOOST = 0.22
/** Dopo un salto la pausa finale si accorcia: resta il tempo di leggere i valori. */
const HOLD_START_AFTER_SKIP_MS = 700

function faceLabel(value: number, e: Entity): string {
  return e.d100Role ? d100FaceLabel(value, e.d100Role) : String(value)
}

/** 20 e 1 naturali sul d20: il dado cambia aspetto appena si ferma. */
function highlightNaturals(entities: Entity[], results: DetectedResult[], pack: LoadedPack | null) {
  results.forEach((r, i) => {
    const e = entities[i]
    if (r.kind !== 'd20' || !e.group || (r.value !== 20 && r.value !== 1)) return
    const tint: DiceTint = r.value === 20 ? 'crit' : 'fumble'
    // Un re-render (pack appena caricato) riapplica il materiale da e.tint.
    e.tint = tint
    const override = pack ? getTintOverride(pack.manifest, tint) : undefined
    const frames = getDiceGeometry(e.kind).faceFrames
    e.group.children.forEach((child, childIdx) => {
      const mesh = child as THREE.Mesh
      mesh.material =
        childIdx === 0
          ? getDiceMaterial(tint, pack, e.kind)
          : getNumeralMaterial(faceLabel(frames[childIdx - 1].value, e), tint, override)
    })
  })
}

type Props = {
  request: SceneRequest | null
  onMount?: () => void
  /** Cambia a ogni tocco sull'overlay: salta l'animazione in corso. */
  skipToken?: number
}

export default function DiceScene({ request, onMount, skipToken }: Props) {
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
      <Orchestrator request={request} onMount={onMount} skipToken={skipToken} />
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

function Orchestrator({ request, onMount, skipToken = 0 }: Props) {
  const worldRef = useRef<DiceWorld | null>(null)
  if (!worldRef.current) worldRef.current = createDiceWorld()

  const entitiesRef = useRef<Entity[]>([])
  const simRef = useRef<RollSimulation | null>(null)
  const holdMsRef = useRef<number | null>(null)
  const finishedRef = useRef(true)
  const skippedRef = useRef(false)
  const [version, setVersion] = useState(0)
  const { invalidate, camera, size } = useThree()
  const { pack } = useDicePack()
  const onMountRef = useRef(onMount)
  onMountRef.current = onMount

  const onCompleteRef = useRef<((results: DetectedResult[]) => void) | undefined>(undefined)
  const onSettledRef = useRef<((results: DetectedResult[]) => void) | undefined>(undefined)
  useEffect(() => {
    onCompleteRef.current = request?.onComplete
    onSettledRef.current = request?.onSettled
  }, [request])

  useEffect(() => {
    if (!(camera instanceof THREE.PerspectiveCamera)) return
    updateWalls(worldRef.current!, camera, size)
  }, [camera, size])

  useEffect(() => {
    onMountRef.current?.()
  }, [])

  // Tocco sull'overlay: durante il lancio accelera la fisica, durante la
  // pausa finale chiude subito.
  useEffect(() => {
    if (skipToken === 0) return
    if (holdMsRef.current !== null) holdMsRef.current = Math.max(holdMsRef.current, HOLD_MS)
    else if (simRef.current) {
      skippedRef.current = true
      simRef.current.skip()
    }
  }, [skipToken])

  useEffect(() => {
    simRef.current?.dispose()
    simRef.current = null
    holdMsRef.current = null
    skippedRef.current = false
    finishedRef.current = true
    entitiesRef.current = []

    if (!request) {
      // Svuota la scena: al tiro dopo non deve ricomparire l'ultimo fotogramma.
      setVersion((v) => v + 1)
      invalidate()
      return
    }

    const specs: SimDieSpec[] = []
    const entities: Entity[] = []
    request.groups.forEach((g, groupIndex) => {
      const kind: Exclude<DiceKind, 'd100'> = g.kind === 'd100' ? 'd10' : g.kind
      const bodyCount = (g.count ?? 1) * (g.kind === 'd100' ? 2 : 1)
      for (let i = 0; i < bodyCount; i++) {
        specs.push({ kind, groupIndex })
        entities.push({
          group: null,
          kind,
          tint: g.tint ?? 'normal',
          d100Role: g.kind === 'd100' ? (i % 2 === 0 ? 'tens' : 'units') : null,
        })
      }
    })
    simRef.current = createRollSimulation(worldRef.current!, specs)
    entitiesRef.current = entities
    finishedRef.current = false
    setVersion((v) => v + 1)

    let raf = 0
    const tick = () => {
      invalidate()
      if (!finishedRef.current) raf = requestAnimationFrame(tick)
    }
    tick()
    return () => cancelAnimationFrame(raf)
  }, [request, invalidate])

  useFrame((_, delta) => {
    const sim = simRef.current
    if (!sim || finishedRef.current) return
    const entities = entitiesRef.current

    if (holdMsRef.current === null) {
      sim.advance(delta)
      sim.dice.forEach((d, i) => {
        const g = entities[i].group
        if (!g) return
        if (sim.phase === 'settled') {
          // La lettura e la pausa finale usano lo stato canonico: l'interpolazione
          // può restare un substep indietro.
          g.position.set(d.body.position.x, d.body.position.y, d.body.position.z)
          g.quaternion.set(d.body.quaternion.x, d.body.quaternion.y, d.body.quaternion.z, d.body.quaternion.w)
        } else {
          const p = d.body.interpolatedPosition
          const q = d.body.interpolatedQuaternion
          g.position.set(p.x, p.y, p.z)
          g.quaternion.set(q.x, q.y, q.z, q.w)
        }
      })
      if (sim.phase === 'settled') {
        holdMsRef.current = skippedRef.current ? HOLD_START_AFTER_SKIP_MS : 0
        highlightNaturals(entities, sim.results(), pack)
        onSettledRef.current?.(sim.results())
      }
      return
    }

    holdMsRef.current += Math.min(delta, 1 / 15) * 1000
    const elapsed = holdMsRef.current
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
    for (const e of entities) e.group?.scale.setScalar(scale)
    if (elapsed >= HOLD_MS) {
      finishedRef.current = true
      onCompleteRef.current?.(sim.results())
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
                  material={getNumeralMaterial(faceLabel(ff.value, e), e.tint, override)}
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
